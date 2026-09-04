$ErrorActionPreference = "Stop"

$baseUrl = "http://127.0.0.1:8000"
$campaignName = "Kind acceptance $(Get-Date -Format 'yyyyMMdd-HHmmss')"
$createBody = "name=$([uri]::EscapeDataString($campaignName))"

$createResponse = Invoke-WebRequest `
    -Uri "$baseUrl/campaigns" `
    -Method Post `
    -ContentType "application/x-www-form-urlencoded" `
    -Body $createBody `
    -UseBasicParsing

$campaignMatch = [regex]::Match(
    $createResponse.Content,
    "/campaigns/([0-9a-f]{32})"
)
if (-not $campaignMatch.Success) {
    throw "Campaign ID was not present in the create response."
}

$campaignId = $campaignMatch.Groups[1].Value

$characterResponse = Invoke-WebRequest `
    -Uri "$baseUrl/campaigns/$campaignId/characters" `
    -Method Post `
    -ContentType "application/x-www-form-urlencoded" `
    -Body @{
        name = "Aria"
        ancestry = "Human"
        class_name = "Fighter"
        level = 5
        armor_class = 18
        hit_point_max = 44
        strength = 18
        dexterity = 14
        constitution = 16
        intelligence = 8
        wisdom = 12
        charisma = 10
        perception_proficient = "true"
    } `
    -UseBasicParsing
if ($characterResponse.Content -notmatch "Passive Perception 14") {
    throw "Character derived statistics were not rendered correctly."
}

$monsterResponse = Invoke-WebRequest `
    -Uri "$baseUrl/campaigns/$campaignId/monsters" `
    -Method Post `
    -ContentType "application/x-www-form-urlencoded" `
    -Body @{
        name = "Ash Drake"
        size = "Large"
        creature_type = "dragon"
        challenge_rating = 5
        armor_class = 17
        hit_point_max = 95
        speed = "40 ft., fly 60 ft."
        primary_ability = "strength"
        strength = 18
        dexterity = 14
        constitution = 16
        intelligence = 8
        wisdom = 12
        charisma = 10
        traits = "Heated Body"
        actions = "Bite`nCinder Breath"
    } `
    -UseBasicParsing
if ($monsterResponse.Content -notmatch "Attack \+7") {
    throw "Monster derived statistics were not rendered correctly."
}

$story = [uri]::EscapeDataString(
    "A lost observatory above a storm-wrapped mountain town."
)

Invoke-WebRequest `
    -Uri "$baseUrl/campaigns/$campaignId/generate/campaign-pack" `
    -Method Post `
    -ContentType "application/x-www-form-urlencoded" `
    -Body "story_prompt=$story" `
    -UseBasicParsing | Out-Null

$deadline = (Get-Date).AddMinutes(15)
$page = $null
do {
    $page = (
        Invoke-WebRequest `
            -Uri "$baseUrl/campaigns/$campaignId" `
            -UseBasicParsing `
            -TimeoutSec 30
    ).Content
    $job = [regex]::Match(
        $page,
        'campaign_pack</strong>\s*<div class="muted">([^<]+)'
    )

    if ($job.Success) {
        $status = $job.Groups[1].Value.Trim()
        Write-Host $status
        if ($status -like "error*") {
            throw "Campaign generation failed: $status"
        }
        if ($status -like "done*") {
            break
        }
    }

    Start-Sleep -Seconds 15
} while ((Get-Date) -lt $deadline)

if (-not $job.Success -or $status -notlike "done*") {
    throw "Campaign generation did not complete within 15 minutes."
}
if ($page -notmatch "Aria" -or $page -notmatch "Ash Drake") {
    throw "Campaign actors did not persist during campaign generation."
}

$requiredKinds = @(
    "file.campaign_pack_json",
    "file.campaign_pack_pdf",
    "file.flowchart_mermaid",
    "file.flowchart_dot",
    "file.map_png"
)
foreach ($kind in $requiredKinds) {
    if ($page -notmatch [regex]::Escape($kind)) {
        throw "Campaign is missing required artifact kind: $kind"
    }
}

$artifactPaths = [regex]::Matches(
    $page,
    'href="(/artifacts/[0-9a-f]+)"'
) | ForEach-Object {
    $_.Groups[1].Value
} | Sort-Object -Unique

$contentTypes = foreach ($path in $artifactPaths) {
    $artifact = Invoke-WebRequest -Uri "$baseUrl$path" -UseBasicParsing
    if ($artifact.StatusCode -ne 200 -or $artifact.RawContentLength -eq 0) {
        throw "Artifact download failed: $path"
    }
    $artifact.Headers["Content-Type"]
}

if (-not ($contentTypes -contains "application/json")) {
    throw "Generated campaign JSON could not be downloaded."
}
if (-not ($contentTypes -contains "application/pdf")) {
    throw "Generated campaign PDF could not be downloaded."
}

Write-Host "Campaign $campaignId generated with all required downloadable artifacts."
