param(
  [string]$RulesPath = 'picks/paper_trading_rules.json',
  [string]$PricesPath = 'picks/paper_price_snapshot.json',
  [string]$StatePath = 'picks/paper_trading_state.json',
  [string]$LedgerPath = 'picks/paper_trading_ledger.csv',
  [decimal]$InitialCash = 100000000
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Resolve-WorkspacePath {
  param([string]$Path)
  if ([System.IO.Path]::IsPathRooted($Path)) {
    return $Path
  }
  return Join-Path (Get-Location) $Path
}

function Get-JsonFile {
  param([string]$Path)
  $resolved = Resolve-WorkspacePath $Path
  if (-not (Test-Path $resolved)) {
    throw "Missing JSON file: $resolved"
  }
  return Get-Content -Path $resolved -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Save-JsonFile {
  param(
    [string]$Path,
    [object]$Value
  )
  $resolved = Resolve-WorkspacePath $Path
  $dir = Split-Path -Parent $resolved
  if (-not (Test-Path $dir)) {
    New-Item -Path $dir -ItemType Directory | Out-Null
  }
  $Value | ConvertTo-Json -Depth 20 | Set-Content -Path $resolved -Encoding UTF8
}

function Get-Position {
  param(
    [object]$State,
    [string]$Ticker
  )
  return $State.positions | Where-Object ticker -eq $Ticker | Select-Object -First 1
}

function Append-Ledger {
  param(
    [string]$Path,
    [string]$Timestamp,
    [string]$Ticker,
    [string]$Name,
    [string]$Side,
    [int]$Quantity,
    [decimal]$Price,
    [decimal]$Notional,
    [string]$Reason
  )

  $resolved = Resolve-WorkspacePath $Path
  if (-not (Test-Path $resolved)) {
    'timestamp,ticker,name,side,quantity,price,notional,reason' | Set-Content -Path $resolved -Encoding UTF8
  }
  ('{0},{1},{2},{3},{4},{5},{6},{7}' -f $Timestamp, $Ticker, $Name, $Side, $Quantity, $Price, $Notional, $Reason) |
    Add-Content -Path $resolved -Encoding UTF8
}

$rules = Get-JsonFile $RulesPath
$prices = Get-JsonFile $PricesPath
$stateResolved = Resolve-WorkspacePath $StatePath

if (Test-Path $stateResolved) {
  $state = Get-Content -Path $stateResolved -Raw -Encoding UTF8 | ConvertFrom-Json
} else {
  $state = [pscustomobject]@{
    mode = 'paper'
    cash = [decimal]$InitialCash
    realized_pnl = [decimal]0
    positions = @()
    executed_events = @()
    last_run = $null
  }
}

if ($null -eq $state.executed_events) {
  $state | Add-Member -MemberType NoteProperty -Name executed_events -Value @()
}

$timestamp = if ($prices.date) { [string]$prices.date } else { (Get-Date).ToString('yyyy-MM-ddTHH:mm:ssK') }
$orders = New-Object System.Collections.Generic.List[object]

foreach ($rule in $rules.positions) {
  if ($rule.status -ne 'active') {
    continue
  }

  $priceProperty = $prices.prices.PSObject.Properties[$rule.ticker]
  if ($null -eq $priceProperty) {
    $orders.Add([pscustomobject]@{
      ticker = $rule.ticker
      action = 'SKIP'
      reason = 'missing_price'
    }) | Out-Null
    continue
  }

  $price = [decimal]$priceProperty.Value
  $position = Get-Position -State $state -Ticker $rule.ticker

  if ($null -ne $position) {
    $pos = $position
    $quantity = [int]$pos.quantity
    if ($quantity -le 0) {
      continue
    }

    if ($price -le [decimal]$rule.stop_loss) {
      $notional = $quantity * $price
      $costBasis = [decimal]$pos.avg_price * $quantity
      $state.cash = [decimal]$state.cash + $notional
      $state.realized_pnl = [decimal]$state.realized_pnl + ($notional - $costBasis)
      $state.positions = @($state.positions | Where-Object ticker -ne $rule.ticker)
      Append-Ledger -Path $LedgerPath -Timestamp $timestamp -Ticker $rule.ticker -Name $rule.name -Side 'SELL' -Quantity $quantity -Price $price -Notional $notional -Reason 'stop_loss'
      $orders.Add([pscustomobject]@{ ticker = $rule.ticker; action = 'SELL'; quantity = $quantity; reason = 'stop_loss' }) | Out-Null
      continue
    }

    if ($price -ge [decimal]$rule.target) {
      $targetEventKey = '{0}:target_hit:{1}' -f $rule.ticker, $rule.target
      if ($state.executed_events -contains $targetEventKey) {
        $orders.Add([pscustomobject]@{ ticker = $rule.ticker; action = 'HOLD'; quantity = $quantity; reason = 'target_tier_already_executed' }) | Out-Null
        continue
      }

      $sellQuantity = [Math]::Max(1, [Math]::Floor($quantity * [decimal]$rule.target_sell_ratio))
      $notional = $sellQuantity * $price
      $costBasis = [decimal]$pos.avg_price * $sellQuantity
      $state.cash = [decimal]$state.cash + $notional
      $state.realized_pnl = [decimal]$state.realized_pnl + ($notional - $costBasis)
      $pos.quantity = $quantity - $sellQuantity
      if ($pos.quantity -le 0) {
        $state.positions = @($state.positions | Where-Object ticker -ne $rule.ticker)
      }
      $state.executed_events += $targetEventKey
      Append-Ledger -Path $LedgerPath -Timestamp $timestamp -Ticker $rule.ticker -Name $rule.name -Side 'SELL' -Quantity $sellQuantity -Price $price -Notional $notional -Reason 'target_hit'
      $orders.Add([pscustomobject]@{ ticker = $rule.ticker; action = 'SELL'; quantity = $sellQuantity; reason = 'target_hit' }) | Out-Null
    } else {
      $orders.Add([pscustomobject]@{ ticker = $rule.ticker; action = 'HOLD'; quantity = $quantity; reason = 'position_open' }) | Out-Null
    }
    continue
  }

  if ($price -ge [decimal]$rule.entry_low -and $price -le [decimal]$rule.entry_high) {
    $maxNotional = [decimal]$state.cash * ([decimal]$rule.max_position_pct / 100)
    $quantityToBuy = [Math]::Floor($maxNotional / $price)
    if ($quantityToBuy -lt 1) {
      $orders.Add([pscustomobject]@{ ticker = $rule.ticker; action = 'SKIP'; reason = 'insufficient_sizing_cash' }) | Out-Null
      continue
    }

    $notional = $quantityToBuy * $price
    $state.cash = [decimal]$state.cash - $notional
    $state.positions += [pscustomobject]@{
      ticker = $rule.ticker
      name = $rule.name
      quantity = [int]$quantityToBuy
      avg_price = $price
      opened_at = $timestamp
    }
    Append-Ledger -Path $LedgerPath -Timestamp $timestamp -Ticker $rule.ticker -Name $rule.name -Side 'BUY' -Quantity $quantityToBuy -Price $price -Notional $notional -Reason 'entry_zone'
    $orders.Add([pscustomobject]@{ ticker = $rule.ticker; action = 'BUY'; quantity = $quantityToBuy; reason = 'entry_zone' }) | Out-Null
  } else {
    $orders.Add([pscustomobject]@{ ticker = $rule.ticker; action = 'WAIT'; reason = 'outside_entry_zone' }) | Out-Null
  }
}

$state.last_run = $timestamp
Save-JsonFile -Path $StatePath -Value $state

[pscustomobject]@{
  mode = 'paper'
  timestamp = $timestamp
  cash = $state.cash
  realized_pnl = $state.realized_pnl
  orders = $orders
} | ConvertTo-Json -Depth 10
