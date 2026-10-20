# Register the collectors as Windows scheduled tasks.
#
#   .\setup_scheduler.ps1            # register all tasks
#   .\setup_scheduler.ps1 -Remove    # unregister them again
#
# Uses pythonw.exe so no console window appears on every run. Output goes to logs/.

param([switch]$Remove)

$ErrorActionPreference = 'Stop'

$repo = $PSScriptRoot
$py   = Join-Path $repo '.venv\Scripts\pythonw.exe'
$src  = Join-Path $repo 'src'

$tasks = @(
    @{ Name = 'WMATA Predictions';     Script = 'collect_wmata.py';           Minutes = 1  },
    @{ Name = 'WMATA GTFS-RT';         Script = 'collect_gtfs_rt.py';         Minutes = 1  },
    @{ Name = 'WMATA Train Positions'; Script = 'collect_train_positions.py'; Minutes = 1  },
    @{ Name = 'WMATA Incidents';       Script = 'collect_incidents.py';       Minutes = 5  },
    @{ Name = 'WMATA Weather';         Script = 'collect_weather.py';         Minutes = 15 },
    @{ Name = 'WMATA GTFS Static';     Script = 'collect_gtfs.py';            Weekly  = $true }
)

if ($Remove) {
    foreach ($t in $tasks) {
        try {
            Unregister-ScheduledTask -TaskName $t.Name -Confirm:$false
            Write-Host "removed: $($t.Name)"
        } catch {
            Write-Host "not registered: $($t.Name)"
        }
    }
    return
}

if (-not (Test-Path $py)) {
    throw "Virtual environment not found at $py. Create it first:`n" +
          "  python -m venv .venv`n" +
          "  .\.venv\Scripts\Activate.ps1`n" +
          "  pip install -r requirements.txt"
}

if (-not (Test-Path (Join-Path $repo '.env'))) {
    throw "No .env file found. Add your WMATA_API_KEY before scheduling collection."
}

# IgnoreNew: if a run is still going when the next fires, skip it rather than letting two
# processes append to the same file.
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

foreach ($t in $tasks) {
    $action = New-ScheduledTaskAction -Execute $py `
        -Argument "`"$(Join-Path $src $t.Script)`"" -WorkingDirectory $repo

    if ($t.Weekly) {
        $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 4am
    } else {
        $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
            -RepetitionInterval (New-TimeSpan -Minutes $t.Minutes) `
            -RepetitionDuration (New-TimeSpan -Days 3650)
    }

    Register-ScheduledTask -TaskName $t.Name -Action $action -Trigger $trigger `
        -Settings $settings -Force | Out-Null

    $cadence = if ($t.Weekly) { 'weekly' } else { "every $($t.Minutes) min" }
    Write-Host "registered: $($t.Name) ($cadence)"
}

Write-Host ''
Write-Host 'Collection is now scheduled. Verify with:'
Write-Host '  Get-Content logs\wmata_predictions.log -Tail 5 -Wait'
