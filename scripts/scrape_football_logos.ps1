$ErrorActionPreference = "Stop"

$countries = @("england", "france", "germany", "italy", "spain", "portugal", "netherlands", "belgium", "turkey")

$baseUrl = "https://football-logos.cc"

$leagueMapping = @{}
$clubMapping = @{}

$leagueKeywords = @("premier-league", "championship", "ligue-1", "ligue-2", "bundesliga", "serie-a", "serie-b", "la-liga", "segunda", "primeira-liga", "eredivisie", "jupiler-pro-league", "super-lig")

foreach ($country in $countries) {
    Write-Host "Scraping $country..." -ForegroundColor Cyan

    try {
        $page = Invoke-WebRequest -Uri "$baseUrl/$country/" -TimeoutSec 30 -UserAgent "Mozilla/5.0"
        $html = $page.Content

        # Extraire toutes les URLs d'assets du pays
        $regex = [regex]"https://assets\.football-logos\.cc/logos/$country/256x256/[a-z0-9-]+\.[a-f0-9]+\.png"
        $matches = $regex.Matches($html)

        $seenUrls = @{}
        foreach ($match in $matches) {
            $url = $match.Value

            if ($seenUrls.ContainsKey($url)) { continue }
            $seenUrls[$url] = $true

            $filename = [System.IO.Path]::GetFileName($url)
            $nameWithoutHash = $filename -replace '\.[a-f0-9]+\.png$', '.png'

            $isLeague = $false
            foreach ($kw in $leagueKeywords) {
                if ($nameWithoutHash -like "*$kw*") {
                    $isLeague = $true
                    break
                }
            }

            if ($isLeague) {
                $leagueKey = $nameWithoutHash -replace '\.[a-f0-9]+$', ''
                if (-not $leagueMapping.ContainsKey($leagueKey)) {
                    $leagueMapping[$leagueKey] = $url
                    Write-Host "  [LEAGUE] $leagueKey -> $url" -ForegroundColor Green
                }
            } else {
                $clubKey = $nameWithoutHash -replace '\.[a-f0-9]+$', ''
                if (-not $clubMapping.ContainsKey($clubKey)) {
                    $clubMapping[$clubKey] = $url
                }
            }
        }

        Write-Host "  Found $($matches.Count) images for $country" -ForegroundColor Gray
    } catch {
        Write-Warning "Error scraping $country : $($_.Exception.Message)"
    }

    Start-Sleep -Milliseconds 500
}

$leagueJson = @{ mapping = $leagueMapping } | ConvertTo-Json -Depth 3
$leagueJson | Out-File -FilePath "data/logos/leagues.json" -Encoding UTF8

$clubJson = @{ mapping = $clubMapping } | ConvertTo-Json -Depth 3
$clubJson | Out-File -FilePath "data/logos/clubs.json" -Encoding UTF8

Write-Host "`nDone!" -ForegroundColor Green
Write-Host "Leagues: $($leagueMapping.Count) logos" -ForegroundColor Green
Write-Host "Clubs: $($clubMapping.Count) logos" -ForegroundColor Green
Write-Host "Files: data/logos/leagues.json, data/logos/clubs.json" -ForegroundColor Green
