' =====================================================================
'  Saipa Mashayekh - one-click installer
'  Double-click this file. It builds the complete Access application,
'  creates (or reuses) the data file, trusts the program folder so the
'  code runs without security prompts, and puts a shortcut on the desktop.
'
'  - Run from a local folder  -> single-PC install (data in Documents).
'  - Run from a network share -> data is kept in <share>\Data and every PC
'    that runs Setup from the same share works on the same data.
'  Running it again upgrades the program and never deletes data.
' =====================================================================
Option Explicit

Const APP_VERSION = "2.0.0"
Const APP_KEY = "SaipaMashayekh"
Const FE_NAME = "SaipaMashayekh.accdb"
Const BE_NAME = "SaipaMashayekh_Data.accdb"

Dim fso, sh, res, setupDir, srcDir, resPath
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")

setupDir = fso.GetParentFolderName(WScript.ScriptFullName)
srcDir = fso.BuildPath(setupDir, "src")
resPath = fso.BuildPath(srcDir, "ui_fa.txt")
If Not fso.FileExists(resPath) Then
    MsgBox "Missing file: " & resPath & vbCrLf & "Extract the whole folder before running Setup.", vbCritical, "Setup"
    WScript.Quit 1
End If
Set res = LoadRes(resPath)

Main
WScript.Quit 0

' ---------------------------------------------------------------------
Sub Main()
    Dim setupUNC, appDir, dataDir, fePath, bePath, tplPath, beExists, feExists
    Dim acc, result, oldFE, warnText, okMsg

    setupUNC = ToUNC(setupDir)
    appDir = fso.BuildPath(sh.ExpandEnvironmentStrings("%LOCALAPPDATA%"), APP_KEY)
    If Left(setupUNC, 2) = "\\" Then
        dataDir = fso.BuildPath(setupUNC, "Data")
    Else
        dataDir = fso.BuildPath(fso.BuildPath(sh.SpecialFolders("MyDocuments"), APP_KEY), "Data")
    End If
    fePath = fso.BuildPath(appDir, FE_NAME)
    bePath = fso.BuildPath(dataDir, BE_NAME)
    tplPath = fso.BuildPath(fso.BuildPath(setupDir, "App"), "SaipaMashayekh_" & APP_VERSION & ".accdb")
    beExists = fso.FileExists(bePath)
    feExists = fso.FileExists(fePath)

    If beExists Then
        okMsg = R("setup.data_existing")
    Else
        okMsg = R("setup.data_new")
    End If
    If MsgBox(Fmt(R("setup.confirm"), Array(bePath, okMsg, appDir)), vbOKCancel + vbQuestion, R("setup.title")) <> vbOK Then Exit Sub

    EnsureFolder appDir
    EnsureFolder dataDir
    TrustLocation appDir

    ' Keep the previous program file as a backup (it holds no data).
    If feExists Then
        oldFE = fso.BuildPath(appDir, "SaipaMashayekh_old_" & Stamp() & ".accdb")
        On Error Resume Next
        fso.MoveFile fePath, oldFE
        If Err.Number <> 0 Then
            On Error GoTo 0
            MsgBox R("setup.fe_locked"), vbExclamation, R("setup.title")
            Exit Sub
        End If
        On Error GoTo 0
    End If

    ' Build with Microsoft Access. If only Access Runtime (or no Access) is
    ' present, fall back to the copy that Setup left in the App folder when
    ' it ran on a PC with full Access (same network folder).
    Dim buildErr
    buildErr = ""
    On Error Resume Next
    Set acc = CreateObject("Access.Application")
    If Err.Number <> 0 Then
        buildErr = R("setup.no_access")
        Set acc = Nothing
    End If
    Err.Clear
    On Error GoTo 0
    If Len(buildErr) = 0 Then
        If CBool(acc.SysCmd(6)) Then   ' acSysCmdRuntime
            buildErr = R("setup.runtime_only")
            acc.Quit
            Set acc = Nothing
        End If
    End If
    If Len(buildErr) > 0 Then
        If fso.FileExists(tplPath) And beExists Then
            fso.CopyFile tplPath, fePath, True
            Finish fePath, feExists, ""
        Else
            RestoreOld oldFE, fePath
            MsgBox buildErr, vbExclamation, R("setup.title")
        End If
        Exit Sub
    End If

    sh.Popup R("setup.working"), 3, R("setup.title"), vbInformation
    result = BuildApp(acc, fePath, bePath)
    If Left(result, 2) <> "OK" Then
        If fso.FileExists(fePath) Then fso.DeleteFile fePath, True
        RestoreOld oldFE, fePath
        MsgBox Fmt(R("setup.failed"), Array(result)), vbCritical, R("setup.title")
        Exit Sub
    End If
    warnText = Mid(result, 3)

    ' Leave a ready-made copy next to Setup so other PCs (even with only the
    ' free Access Runtime) can install from the same network folder.
    On Error Resume Next
    EnsureFolder fso.GetParentFolderName(tplPath)
    fso.CopyFile fePath, tplPath, True
    On Error GoTo 0

    Finish fePath, feExists, warnText
End Sub

Function BuildApp(acc, fePath, bePath)
    Dim f, n, result
    On Error Resume Next
    acc.AutomationSecurity = 1     ' msoAutomationSecurityLow: allow our code
    Err.Clear
    acc.Visible = True
    acc.NewCurrentDatabase fePath
    If Err.Number <> 0 Then
        BuildApp = "NewCurrentDatabase: " & Err.Description
        acc.Quit
        Exit Function
    End If

    n = 0
    For Each f In fso.GetFolder(srcDir).Files
        If LCase(fso.GetExtensionName(f.Name)) = "bas" Then
            LoadModule acc, f.Path
            If Err.Number <> 0 Then
                BuildApp = "LoadModule " & f.Name & ": " & Err.Description
                acc.CloseCurrentDatabase
                acc.Quit
                Exit Function
            End If
            n = n + 1
        End If
    Next
    If n = 0 Then
        BuildApp = "No .bas modules in " & srcDir
        acc.CloseCurrentDatabase
        acc.Quit
        Exit Function
    End If

    result = acc.Run("Mashayekh_Install", bePath, resPath)
    If Err.Number <> 0 Then result = "Mashayekh_Install: " & Err.Description
    Err.Clear
    acc.DoCmd.RunCommand 126      ' acCmdCompileAndSaveAllModules
    Err.Clear
    acc.CloseCurrentDatabase
    acc.Quit
    Set acc = Nothing
    On Error GoTo 0
    BuildApp = CStr(result)
End Function

' Loads a .bas file as a standard module (no "Trust access to the VBA
' project" setting needed). The VB_Name attribute line is removed first.
Sub LoadModule(acc, path)
    Dim ts, txt, lines, i, modName, outText, tmp, ln
    Set ts = fso.OpenTextFile(path, 1)
    txt = ts.ReadAll
    ts.Close
    txt = Replace(Replace(txt, vbCrLf, vbLf), vbCr, vbLf)
    lines = Split(txt, vbLf)
    modName = fso.GetBaseName(path)
    outText = ""
    For i = 0 To UBound(lines)
        ln = lines(i)
        If LCase(Left(ln, 9)) = "attribute" Then
            If InStr(1, ln, "VB_Name", vbTextCompare) > 0 Then
                modName = Trim(Split(ln, """")(1))
            End If
        Else
            outText = outText & ln & vbCrLf
        End If
    Next
    tmp = fso.BuildPath(fso.GetSpecialFolder(2), modName & "_" & Stamp() & ".txt")
    Set ts = fso.CreateTextFile(tmp, True, False)
    ts.Write outText
    ts.Close
    acc.LoadFromText 5, modName, tmp   ' acModule
    fso.DeleteFile tmp, True
End Sub

Sub Finish(fePath, wasUpgrade, warnText)
    Dim lnk, msg
    On Error Resume Next
    Set lnk = sh.CreateShortcut(fso.BuildPath(sh.SpecialFolders("Desktop"), R("setup.shortcut") & ".lnk"))
    lnk.TargetPath = fePath
    lnk.WorkingDirectory = fso.GetParentFolderName(fePath)
    lnk.Description = R("app.title")
    lnk.Save
    On Error GoTo 0
    If wasUpgrade Then
        msg = R("setup.done_upgrade")
    Else
        msg = R("setup.done")
    End If
    If Len(Trim(Replace(warnText, vbCrLf, ""))) > 0 Then msg = R("setup.warnings") & warnText & vbCrLf & vbCrLf & msg
    If MsgBox(msg, vbYesNo + vbInformation, R("setup.title")) = vbYes Then
        sh.Run """" & fePath & """", 1, False
    End If
End Sub

Sub RestoreOld(oldFE, fePath)
    On Error Resume Next
    If Len(oldFE) > 0 Then
        If fso.FileExists(oldFE) And Not fso.FileExists(fePath) Then fso.MoveFile oldFE, fePath
    End If
    On Error GoTo 0
End Sub

' Registers the program folder as an Access "Trusted Location" (current user)
' for Access 2010, 2013 and 2016/2019/2021/2024/365.
Sub TrustLocation(path)
    Dim v, k
    On Error Resume Next
    For Each v In Array("14.0", "15.0", "16.0")
        k = "HKCU\Software\Microsoft\Office\" & v & "\Access\Security\Trusted Locations\" & APP_KEY & "\"
        sh.RegWrite k & "Path", path & "\", "REG_SZ"
        sh.RegWrite k & "AllowSubfolders", 1, "REG_DWORD"
        sh.RegWrite k & "Description", "Saipa Mashayekh", "REG_SZ"
    Next
    On Error GoTo 0
End Sub

' ---------------------------------------------------------------------
Function ToUNC(p)
    Dim drv, d
    ToUNC = p
    If Left(p, 2) = "\\" Then Exit Function
    On Error Resume Next
    drv = fso.GetDriveName(p)
    If Len(drv) = 0 Then Exit Function
    Set d = fso.GetDrive(drv)
    If Err.Number = 0 Then
        If d.DriveType = 3 Then
            If Len(d.ShareName) > 0 Then ToUNC = d.ShareName & Mid(p, Len(drv) + 1)
        End If
    End If
    On Error GoTo 0
End Function

Sub EnsureFolder(p)
    If Len(p) = 0 Then Exit Sub
    If fso.FolderExists(p) Then Exit Sub
    EnsureFolder fso.GetParentFolderName(p)
    fso.CreateFolder p
End Sub

Function Stamp()
    Dim n
    n = Now
    Stamp = Year(n) & Right("0" & Month(n), 2) & Right("0" & Day(n), 2) & "_" & Right("0" & Hour(n), 2) & Right("0" & Minute(n), 2) & Right("0" & Second(n), 2)
End Function

Function LoadRes(path)
    Dim st, txt, ln, p, d
    Set d = CreateObject("Scripting.Dictionary")
    Set st = CreateObject("ADODB.Stream")
    st.Type = 2
    st.Charset = "utf-8"
    st.Open
    st.LoadFromFile path
    txt = st.ReadText(-1)
    st.Close
    txt = Replace(txt, vbCr, "")
    For Each ln In Split(txt, vbLf)
        ln = Trim(ln)
        If Len(ln) > 0 Then
            If AscW(Left(ln, 1)) = &HFEFF Then ln = Mid(ln, 2)
        End If
        If Len(ln) > 0 Then
            If Left(ln, 1) <> "#" Then
                p = InStr(ln, "=")
                If p > 1 Then d(Trim(Left(ln, p - 1))) = Replace(Trim(Mid(ln, p + 1)), "\n", vbCrLf)
            End If
        End If
    Next
    Set LoadRes = d
End Function

Function R(key)
    If res.Exists(key) Then
        R = res(key)
    Else
        R = key
    End If
End Function

Function Fmt(s, args)
    Dim i
    Fmt = s
    For i = 0 To UBound(args)
        Fmt = Replace(Fmt, "{" & i & "}", args(i))
    Next
End Function
