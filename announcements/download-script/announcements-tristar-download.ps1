$date = Get-Date -Format "dd.MM.yyyy-HH-mm-ss"
$date_without_time = $date.Substring(0,10) -replace '\.','_'
$path = "D:\Informatyka\MAGISTERKA\announcements\data\$date_without_time"
If(!(test-path $path))
{
    New-Item -ItemType Directory -Force -Path $path
}

$new_file_path = "$path\kom$date.json"

D:\Informatyka\MAGISTERKA\announcements\download-script\wget.exe https://files.cloudgdansk.pl/d/otwarte-dane/ztm/bsk.json -O $new_file_path
D:\Python39\python3.exe D:\Informatyka\MAGISTERKA\announcements\download-script\transform-json.py $new_file_path