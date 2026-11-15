' Generate Access database for ZOBO Hardware Store
' Run with: cscript //Nologo scripts\generate_access_windows.vbs
'
' This file must stay ASCII-only: cscript reads it as ANSI, so a UTF-8 accent
' would be stored as two wrong characters (mojibake). Accented
' letters are written as \xHH (Unicode code point in hex) and decoded by Dec().

Option Explicit

Dim accessApp, db, sql
Dim dbPath, fso

' Replace each \xHH in s by the character with that code point
Function Dec(s)
    Dim p
    p = InStr(s, "\x")
    Do While p > 0
        s = Left(s, p - 1) & ChrW(CLng("&H" & Mid(s, p + 2, 2))) & Mid(s, p + 4)
        p = InStr(s, "\x")
    Loop
    Dec = s
End Function

' Get absolute path
Set fso = CreateObject("Scripting.FileSystemObject")
dbPath = fso.GetParentFolderName(WScript.ScriptFullName)
dbPath = fso.GetParentFolderName(dbPath) & "\data\STOCK_ZOBO.mdb"

' Delete if exists
If fso.FileExists(dbPath) Then
    fso.DeleteFile dbPath
End If

WScript.Echo "Creating Access database: " & dbPath

' Create new Access database
Set accessApp = CreateObject("Access.Application")
Set db = accessApp.DBEngine.CreateDatabase(dbPath, ";LANGID=0x0409;CP=1252;COUNTRY=0")

' Create Articles table
sql = "CREATE TABLE Articles (" & _
      "id COUNTER PRIMARY KEY, " & _
      "designation VARCHAR(100), " & _
      "unite VARCHAR(20), " & _
      "qty_stock INTEGER, " & _
      "prix_achat CURRENCY, " & _
      "date_modif DATETIME)"

db.Execute sql

' Insert synthetic data with spelling variations
' \xEE = i circumflex, \xEA = e circumflex, \xE2 = a circumflex, \xE9 = e acute,
' \xE0 = a grave, \xEF = i diaeresis, \xB2 = superscript two
Dim products(23)
products(0) = "('Pointes 2.5 pouces', 'Bo\xEEte 500g', 45, 1500, #2026-11-01#)"
products(1) = "('Vis bois 4x40mm', 'Bo\xEEte 100', 120, 850, #2026-11-02#)"
products(2) = "('Clous t\xEAte plate 70mm', 'kg', 8, 2200, #2026-11-03#)"
products(3) = "('Tuyau PVC 32mm', 'Barre 6m', 12, 4800, #2026-11-02#)"  ' low stock (r_stock_replenish)
products(4) = "('Raccord PVC coude 90', 'Unit\xE9', 150, 245, #2026-11-05#)"
products(5) = "('Tuyau PPR 20mm', 'Barre 4m', 18, 3500, #2026-11-06#)"
products(6) = "('C\xE2ble \xE9lectrique 2.5mm\xB2', 'Rouleau 100m', 5, 45000, #2026-11-04#)"
products(7) = "('Interrupteur va-et-vient', 'Unit\xE9', 85, 1250, #2026-11-08#)"
products(8) = "('Prise de courant double', 'Unit\xE9', 72, 2100, #2026-11-09#)"
products(9) = "('Cadenas laiton 40mm', 'Unit\xE9', 35, 3500, #2026-11-10#)"
products(10) = "('Serrure \xE0 mortaiser', 'Unit\xE9', 12, 14000, #2026-11-05#)"  ' >10% above the supplier price
products(11) = "('Penture acier 30cm', 'Paire', 28, 4200, #2026-11-12#)"
products(12) = "('Peinture satin\xE9e blanc', 'Litre', 42, 5500, #2026-11-13#)"
products(13) = "('Pinceau plat 2 pouces', 'Unit\xE9', 95, 1800, #2026-11-14#)"
products(14) = "('Rouleau peinture 10cm', 'Unit\xE9', 67, 2200, #2026-11-15#)"
products(15) = "('Ciment 50 kg', 'Sac', 180, 7500, #2026-11-01#)"
products(16) = "('Ciment-colle 25 kg', 'Sac', 65, 3900, #2026-11-02#)"
products(17) = "('Marteau rivoir 500g', 'Unit\xE9', 22, 5900, #2026-11-03#)"
products(18) = "('Scie \xE9go\xEFne 450mm', 'Unit\xE9', 15, 8500, #2026-11-04#)"
products(19) = "('Perceuse \xE9lectrique 500W', 'Unit\xE9', 8, 52000, #2026-11-03#)"  ' low stock, >10% above the supplier price

' Intentional variations for testing normalization
products(20) = "('ciment 50 kg', 'Sac', 175, 7500, #2026-11-06#)"  ' lowercase
products(21) = "('Ciment50kg', 'Sac', 182, 7600, #2026-11-07#)"    ' no space
products(22) = "('cim\xE9nt 50kg', 'Sac', 9, 7450, #2026-11-08#)"     ' low stock + accent
products(23) = "('ciment (50kg)', 'Sac', 190, 7550, #2026-11-09#)" ' parentheses

Dim i
For i = 0 To 23
    sql = "INSERT INTO Articles (designation, unite, qty_stock, prix_achat, date_modif) VALUES " & Dec(products(i))
    db.Execute sql
Next

WScript.Echo "OK - Created Articles table with " & (i) & " records"
WScript.Echo "OK - Includes 4 intentional variations for normalization testing"

' Close database
db.Close
accessApp.Quit

WScript.Echo "OK - Database created successfully: " & dbPath

Set db = Nothing
Set accessApp = Nothing
Set fso = Nothing
