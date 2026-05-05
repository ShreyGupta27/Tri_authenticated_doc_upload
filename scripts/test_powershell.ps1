# PowerShell script to test the JWT API
$uri = "http://localhost:8000/upload"
$token = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoidGVzdC11c2VyLTEyMyIsImV4cCI6MTc2Nzk3NDYyMX0.BFI8TdVmSjqUBCuk_25Il5CIh2guauKbo8vE3TRMmJY"

# Create a test file
$testContent = "This is a test PDF file content"
$testFile = "test.pdf"
[System.IO.File]::WriteAllText($testFile, $testContent)

# Create the multipart form data
$boundary = [System.Guid]::NewGuid().ToString()
$LF = "`r`n"

$bodyLines = (
    "--$boundary",
    "Content-Disposition: form-data; name=`"auth_method`"$LF",
    "jwt",
    "--$boundary",
    "Content-Disposition: form-data; name=`"file`"; filename=`"test.pdf`"",
    "Content-Type: application/pdf$LF",
    $testContent,
    "--$boundary--$LF"
) -join $LF

# Set headers
$headers = @{
    "Authorization" = $token
    "Content-Type" = "multipart/form-data; boundary=$boundary"
}

Write-Host "Testing JWT authentication with PowerShell..."
Write-Host "Token: $token"
Write-Host ""

try {
    $response = Invoke-RestMethod -Uri $uri -Method Post -Headers $headers -Body $bodyLines
    Write-Host "✅ Success Response:"
    $response | ConvertTo-Json -Depth 3
} catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    $responseBody = $_.Exception.Response | Get-Member -Name 'GetResponseStream' -ErrorAction SilentlyContinue
    
    if ($responseBody) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseText = $reader.ReadToEnd()
        $reader.Close()
        
        Write-Host "Response Status: $statusCode"
        Write-Host "Response Body: $responseText"
        
        if ($statusCode -eq 500 -and $responseText -like "*STORAGE_CONNECTION_FAILED*") {
            Write-Host "✅ JWT Authentication is working! (Storage error is expected)"
        } elseif ($statusCode -eq 401) {
            Write-Host "❌ JWT Authentication failed"
        } else {
            Write-Host "🤔 Unexpected response"
        }
    } else {
        Write-Host "Error: $($_.Exception.Message)"
    }
}

# Clean up
Remove-Item $testFile -ErrorAction SilentlyContinue