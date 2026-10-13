Attribute VB_Name = "modApp"
Option Compare Database
Option Explicit

' =====================================================================
'  Saipa Mashayekh - complaints, office automation and CRM
'  Runtime core: texts, session/login, navigation, generic form buttons,
'  dashboard, back-end link, backups, reports and Jalali (Persian) dates.
'
'  This module is pure ASCII on purpose. Every Persian text is stored in
'  table tblUIText (filled from src\ui_fa.txt by the installer), so the code
'  imports correctly whatever the Windows "non-Unicode" language is.
'  Message boxes use MessageBoxW because VBA MsgBox cannot show Unicode.
' =====================================================================

Public Const APP_VERSION As String = "2.0.0"
Public Const SCHEMA_VERSION As Long = 1

Public Const SQL_CUST As String = "SELECT CustomerID, FullName & ' | ' & Nz(Mobile,'') AS CustomerText FROM tblCustomers ORDER BY FullName"
Public Const SQL_VEH_BASE As String = "SELECT v.VehicleID, v.PlateNumber & ' | ' & Nz(v.ModelName,'') & ' | ' & Nz(c.FullName,'') AS VehicleText FROM tblVehicles AS v LEFT JOIN tblCustomers AS c ON v.CustomerID=c.CustomerID"
Public Const SQL_USR As String = "SELECT UserID, FullName FROM tblUsers ORDER BY FullName"
Public Const SQL_CMP As String = "SELECT k.ComplaintID, k.ComplaintID & ' - ' & k.SubjectText & ' | ' & Nz(c.FullName,'') AS ComplaintText FROM tblComplaints AS k LEFT JOIN tblCustomers AS c ON k.CustomerID=c.CustomerID ORDER BY k.ComplaintID DESC"

Public Const REPORT_LIST As String = "qryRptOpenComplaints;qryRptOverdueComplaints;qryRptPendingApprovals;qryRptComplaintsByStatus;qryRptComplaintsByMonth;qryRptFollowUps;qryRptOverdueTasks;qryRptOpenLetters;qryRptServiceDue;qryRptServicesByType;qryRptCustomers"

Private Declare PtrSafe Function MessageBoxW Lib "user32" (ByVal hWnd As LongPtr, ByVal lpText As LongPtr, ByVal lpCaption As LongPtr, ByVal uType As Long) As Long

Private Const MB_TASKMODAL As Long = &H2000&
Private Const MB_RIGHT As Long = &H80000
Private Const MB_RTLREADING As Long = &H100000

Private mText As Object      ' Scripting.Dictionary: key -> Persian text
Private mLookup As Object    ' Scripting.Dictionary: "Category|Code" -> Persian title

' ---------------------------------------------------------------------
'  Texts, lookups and messages
' ---------------------------------------------------------------------

Public Function T(ByVal key As String) As String
    If mText Is Nothing Then LoadTextCache
    If mText.Exists(key) Then
        T = mText(key)
    Else
        T = key
    End If
End Function

Public Function TF(ByVal key As String, ParamArray args() As Variant) As String
    Dim s As String, i As Long
    s = T(key)
    For i = LBound(args) To UBound(args)
        s = Replace(s, "{" & i & "}", Nz(args(i), ""))
    Next i
    TF = s
End Function

Private Sub LoadTextCache()
    Dim rs As DAO.Recordset
    Set mText = CreateObject("Scripting.Dictionary")
    mText.CompareMode = 1
    On Error GoTo Done
    Set rs = CurrentDb.OpenRecordset("SELECT TextKey, TextValue FROM tblUIText", dbOpenSnapshot)
    Do Until rs.EOF
        mText(CStr(rs!TextKey)) = Nz(rs!TextValue, "")
        rs.MoveNext
    Loop
    rs.Close
Done:
End Sub

Public Function LK(ByVal category As String, ByVal code As Variant) As String
    Dim k As String
    If IsNull(code) Then Exit Function
    If mLookup Is Nothing Then LoadLookupCache
    k = category & "|" & CStr(code)
    If mLookup.Exists(k) Then
        LK = mLookup(k)
    Else
        LK = CStr(code)
    End If
End Function

Private Sub LoadLookupCache()
    Dim rs As DAO.Recordset
    Set mLookup = CreateObject("Scripting.Dictionary")
    mLookup.CompareMode = 1
    On Error GoTo Done
    Set rs = CurrentDb.OpenRecordset("SELECT Category, Code, TitleFa FROM tblLookups", dbOpenSnapshot)
    Do Until rs.EOF
        mLookup(rs!Category & "|" & rs!Code) = Nz(rs!TitleFa, "")
        rs.MoveNext
    Loop
    rs.Close
Done:
End Sub

Public Function ResetCaches() As Boolean
    Set mText = Nothing
    Set mLookup = Nothing
    ResetCaches = True
End Function

Public Function AppTitle() As String
    AppTitle = T("app.title")
    If AppTitle = "app.title" Then AppTitle = "Saipa Mashayekh"
End Function

' Unicode, right-to-left message box. Returns vbOK, vbYes, vbNo, ...
Public Function Msg(ByVal msgText As String, Optional ByVal buttons As Long = vbInformation, Optional ByVal title As String = "") As Long
    If Len(title) = 0 Then title = AppTitle()
    Msg = MessageBoxW(Application.hWndAccessApp, StrPtr(msgText), StrPtr(title), buttons Or MB_TASKMODAL Or MB_RIGHT Or MB_RTLREADING)
End Function

Public Function Confirm(ByVal msgText As String) As Boolean
    Confirm = (Msg(msgText, vbYesNo + vbQuestion + vbDefaultButton2) = vbYes)
End Function

Public Sub ShowError(Optional ByVal context As String = "")
    Dim d As String
    d = Err.Description
    If Len(context) > 0 Then d = d & vbCrLf & "(" & context & ")"
    Msg T("err.prefix") & vbCrLf & d, vbExclamation
End Sub

Public Function SqlStr(ByVal s As String) As String
    SqlStr = "'" & Replace(s, "'", "''") & "'"
End Function

' Unicode input box (VBA InputBox is not Unicode). Returns Null on cancel.
Public Function AskText(ByVal promptText As String, Optional ByVal defaultValue As String = "", Optional ByVal isPassword As Boolean = False) As Variant
    SetTempVar "PromptText", promptText
    SetTempVar "PromptDefault", defaultValue
    SetTempVar "PromptPwd", isPassword
    SetTempVar "PromptOK", False
    SetTempVar "PromptResult", ""
    DoCmd.OpenForm "frmPrompt", acNormal, , , , acDialog
    If TempVars("PromptOK") Then
        AskText = CStr(Nz(TempVars("PromptResult"), ""))
    Else
        AskText = Null
    End If
End Function

Public Function PromptLoad() As Boolean
    Dim f As Form
    Set f = Forms("frmPrompt")
    f.Controls("lblPrompt").Caption = Nz(TempVars("PromptText"), "")
    If TempVars("PromptPwd") Then f.Controls("txtValue").InputMask = "Password"
    If Len(Nz(TempVars("PromptDefault"), "")) > 0 Then f.Controls("txtValue").Value = TempVars("PromptDefault")
    PromptLoad = True
End Function

Public Function PromptOK() As Boolean
    SetTempVar "PromptResult", CStr(Nz(Forms("frmPrompt").Controls("txtValue").Value, ""))
    SetTempVar "PromptOK", True
    DoCmd.Close acForm, "frmPrompt"
    PromptOK = True
End Function

Public Function PromptCancel() As Boolean
    SetTempVar "PromptOK", False
    DoCmd.Close acForm, "frmPrompt"
    PromptCancel = True
End Function

' ---------------------------------------------------------------------
'  Session
' ---------------------------------------------------------------------

Public Sub SetTempVar(ByVal varName As String, ByVal v As Variant)
    On Error Resume Next
    TempVars.Remove varName
    On Error GoTo 0
    TempVars.Add varName, v
End Sub

Public Function CurrentUserID() As Long
    On Error Resume Next
    CurrentUserID = Nz(TempVars("UserID"), 0)
End Function

Public Function CurrentRole() As String
    On Error Resume Next
    CurrentRole = Nz(TempVars("RoleCode"), "")
End Function

Public Function IsAdmin() As Boolean
    IsAdmin = (CurrentRole() = "ADMIN")
End Function

Public Function IsManager() As Boolean
    IsManager = (CurrentRole() = "ADMIN" Or CurrentRole() = "MANAGER")
End Function

' Experts, managers and admins may submit corrective-action plans and results.
Public Function CanWork() As Boolean
    CanWork = (IsManager() Or CurrentRole() = "EXPERT")
End Function

Public Sub LogEvent(ByVal userID As Long, ByVal eventCode As String, Optional ByVal details As String = "")
    On Error Resume Next
    Dim rs As DAO.Recordset
    Set rs = CurrentDb.OpenRecordset("SELECT * FROM tblAuditLog WHERE 1=0", dbOpenDynaset)
    rs.AddNew
    If userID > 0 Then rs!UserID = userID
    rs!EventCode = eventCode
    rs!DetailsText = Left$(details, 255)
    rs!MachineName = Left$(Environ$("COMPUTERNAME") & "\" & Environ$("USERNAME"), 64)
    rs!EventAt = Now()
    rs.Update
    rs.Close
End Sub

Public Function GetAppSetting(ByVal settingName As String, Optional ByVal defaultValue As String = "") As String
    On Error Resume Next
    GetAppSetting = Nz(DLookup("SettingValue", "tblSettings", "SettingName=" & SqlStr(settingName)), defaultValue)
End Function

Public Sub SetAppSetting(ByVal settingName As String, ByVal settingValue As String)
    Dim db As DAO.Database
    Set db = CurrentDb
    db.Execute "UPDATE tblSettings SET SettingValue=" & SqlStr(settingValue) & " WHERE SettingName=" & SqlStr(settingName), dbFailOnError
    If db.RecordsAffected = 0 Then
        db.Execute "INSERT INTO tblSettings (SettingName, SettingValue) VALUES (" & SqlStr(settingName) & "," & SqlStr(settingValue) & ")", dbFailOnError
    End If
End Sub

' ---------------------------------------------------------------------
'  Start-up, back-end link, login
' ---------------------------------------------------------------------

' OnLoad of frmLogin (the start-up form).
Public Function AppStartup() As Boolean
    On Error GoTo Fail
    If Not Application.UserControl Then Exit Function   ' opened by the installer
    ResetCaches
    If Not EnsureBackendLink() Then
        Application.Quit acQuitSaveNone
        Exit Function
    End If
    If CLng(Val(GetAppSetting("SchemaVersion", "0"))) > SCHEMA_VERSION Then
        Msg T("msg.update_needed"), vbExclamation
    End If
    On Error Resume Next
    Forms("frmLogin").Controls("txtUser").SetFocus
    AppStartup = True
    Exit Function
Fail:
    ShowError "AppStartup"
End Function

Public Function BackendPath() As String
    Dim c As String, p As Long
    On Error Resume Next
    c = CurrentDb.TableDefs("tblUsers").Connect
    p = InStr(1, c, "DATABASE=", vbTextCompare)
    If p > 0 Then
        c = Mid$(c, p + 9)
        p = InStr(c, ";")
        If p > 0 Then c = Left$(c, p - 1)
        BackendPath = c
    End If
End Function

Public Function BackendReachable() As Boolean
    Dim rs As DAO.Recordset
    On Error GoTo No
    Set rs = CurrentDb.OpenRecordset("SELECT TOP 1 UserID FROM tblUsers", dbOpenSnapshot)
    rs.Close
    BackendReachable = True
No:
End Function

Public Function EnsureBackendLink() As Boolean
    Dim p As String
    If BackendReachable() Then
        EnsureBackendLink = True
        Exit Function
    End If
    Msg TF("msg.be_not_found", BackendPath()), vbExclamation
    Do
        p = PickFile(T("dlg.pick_be"), "Access", "*.accdb", BackendPath())
        If Len(p) = 0 Then Exit Function
        If RelinkAll(p) Then
            If BackendReachable() Then
                EnsureBackendLink = True
                Exit Function
            End If
        End If
        If Not Confirm(T("msg.be_retry")) Then Exit Function
    Loop
End Function

Public Function RelinkAll(ByVal newPath As String) As Boolean
    Dim db As DAO.Database, td As DAO.TableDef, n As Long
    On Error GoTo Fail
    Set db = CurrentDb
    For Each td In db.TableDefs
        If Left$(td.Connect, 10) = ";DATABASE=" Then
            td.Connect = ";DATABASE=" & newPath
            td.RefreshLink
            n = n + 1
        End If
    Next td
    db.TableDefs.Refresh
    ResetCaches
    RelinkAll = (n > 0)
    Exit Function
Fail:
    Msg TF("msg.relink_failed", Err.Description), vbExclamation
End Function

Public Function PickFile(ByVal dialogTitle As String, ByVal filterName As String, ByVal filterSpec As String, Optional ByVal startPath As String = "") As String
    Dim fd As Object
    On Error GoTo Fail
    Set fd = Application.FileDialog(3)   ' msoFileDialogFilePicker
    fd.Title = dialogTitle
    fd.AllowMultiSelect = False
    fd.Filters.Clear
    fd.Filters.Add filterName, filterSpec
    If Len(startPath) > 0 Then fd.InitialFileName = startPath
    If fd.Show = -1 Then PickFile = ToUNC(fd.SelectedItems(1))
    Exit Function
Fail:
    ShowError "PickFile"
End Function

' Converts a mapped network drive path (Z:\...) to its UNC form (\\server\share\...).
Public Function ToUNC(ByVal p As String) As String
    Dim fso As Object, drv As String, d As Object
    ToUNC = p
    If Left$(p, 2) = "\\" Then Exit Function
    On Error GoTo Done
    Set fso = CreateObject("Scripting.FileSystemObject")
    drv = fso.GetDriveName(p)
    If Len(drv) = 0 Then Exit Function
    Set d = fso.GetDrive(drv)
    If d.DriveType = 3 Then
        If Len(d.ShareName) > 0 Then ToUNC = d.ShareName & Mid$(p, Len(drv) + 1)
    End If
Done:
End Function

Public Function DoLogin() As Boolean
    Dim f As Form, uName As String, pwd As String, rs As DAO.Recordset, uid As Long
    On Error GoTo Fail
    Set f = Forms("frmLogin")
    uName = Trim$(NormDigits(Nz(f.Controls("txtUser").Value, "")))
    pwd = Nz(f.Controls("txtPwd").Value, "")
    If Len(uName) = 0 Or Len(pwd) = 0 Then
        Msg T("msg.login_empty"), vbExclamation
        Exit Function
    End If
    Set rs = CurrentDb.OpenRecordset("SELECT * FROM tblUsers WHERE UserName=" & SqlStr(uName), dbOpenDynaset)
    If rs.EOF Then
        LogEvent 0, "LOGIN_FAIL", uName
        Msg T("msg.login_wrong"), vbExclamation
        GoTo Cleanup
    End If
    uid = rs!UserID
    If Not rs!IsActive Then
        Msg T("msg.user_inactive"), vbExclamation
        GoTo Cleanup
    End If
    If Len(Nz(rs!PwdHash, "")) = 0 Then
        Msg T("msg.no_password"), vbExclamation
        GoTo Cleanup
    End If
    If Not VerifyPassword(pwd, Nz(rs!PwdSalt, ""), Nz(rs!PwdHash, "")) Then
        rs.Edit
        rs!FailedLogins = Nz(rs!FailedLogins, 0) + 1
        rs.Update
        LogEvent uid, "LOGIN_FAIL", uName
        Msg T("msg.login_wrong"), vbExclamation
        f.Controls("txtPwd").Value = Null
        GoTo Cleanup
    End If

    rs.Edit
    rs!FailedLogins = 0
    rs!LastLoginAt = Now()
    rs.Update
    SetTempVar "UserID", uid
    SetTempVar "RoleCode", CStr(Nz(rs!RoleCode, "STAFF"))
    SetTempVar "UserFullName", CStr(Nz(rs!FullName, uName))
    SetTempVar "LoggingOut", False
    LogEvent uid, "LOGIN"
    DailyBackup

    If rs!MustChangePwd Then
        rs.Close
        DoCmd.Close acForm, "frmLogin"
        Msg T("msg.must_change_pwd"), vbInformation
        DoCmd.OpenForm "frmChangePassword", acNormal, , , , , "FORCE"
    Else
        rs.Close
        DoCmd.Close acForm, "frmLogin"
        DoCmd.OpenForm "frmMain"
    End If
    DoLogin = True
    Exit Function
Cleanup:
    rs.Close
    Exit Function
Fail:
    ShowError "DoLogin"
End Function

Public Function ChangePwdLoad() As Boolean
    Dim f As Form
    Set f = Forms("frmChangePassword")
    f.Controls("lblForce").Visible = (Nz(f.OpenArgs, "") = "FORCE")
    ChangePwdLoad = True
End Function

Public Function DoChangePassword() As Boolean
    Dim f As Form, oldPwd As String, new1 As String, new2 As String, rs As DAO.Recordset, salt As String
    On Error GoTo Fail
    Set f = Forms("frmChangePassword")
    oldPwd = Nz(f.Controls("txtOld").Value, "")
    new1 = Nz(f.Controls("txtNew").Value, "")
    new2 = Nz(f.Controls("txtNew2").Value, "")
    If CurrentUserID() = 0 Then Msg T("err.login_required"), vbExclamation: Exit Function
    If Len(new1) < MIN_PASSWORD_LEN Then Msg TF("msg.pwd_short", MIN_PASSWORD_LEN), vbExclamation: Exit Function
    If new1 <> new2 Then Msg T("msg.pwd_mismatch"), vbExclamation: Exit Function
    If new1 = oldPwd Then Msg T("msg.pwd_same"), vbExclamation: Exit Function
    Set rs = CurrentDb.OpenRecordset("SELECT * FROM tblUsers WHERE UserID=" & CurrentUserID(), dbOpenDynaset)
    If Not VerifyPassword(oldPwd, Nz(rs!PwdSalt, ""), Nz(rs!PwdHash, "")) Then
        rs.Close
        Msg T("msg.old_pwd_wrong"), vbExclamation
        Exit Function
    End If
    salt = NewSalt()
    rs.Edit
    rs!PwdSalt = salt
    rs!PwdHash = HashPassword(new1, salt)
    rs!MustChangePwd = False
    rs.Update
    rs.Close
    LogEvent CurrentUserID(), "PWD_CHANGE"
    DoCmd.Close acForm, "frmChangePassword"
    Msg T("msg.pwd_changed"), vbInformation
    If Not IsFormLoaded("frmMain") Then DoCmd.OpenForm "frmMain"
    DoChangePassword = True
    Exit Function
Fail:
    ShowError "DoChangePassword"
End Function

Public Function ChangePwdCancel() As Boolean
    Dim forced As Boolean
    forced = (Nz(Forms("frmChangePassword").OpenArgs, "") = "FORCE")
    DoCmd.Close acForm, "frmChangePassword"
    If forced Then AppLogout
    ChangePwdCancel = True
End Function

Public Function AppLogout() As Boolean
    Dim i As Long
    On Error Resume Next
    LogEvent CurrentUserID(), "LOGOUT"
    SetTempVar "LoggingOut", True
    For i = Forms.Count - 1 To 0 Step -1
        DoCmd.Close acForm, Forms(i).Name
    Next i
    TempVars.RemoveAll
    DoCmd.OpenForm "frmLogin"
    AppLogout = True
End Function

Public Function AppExit() As Boolean
    If CurrentUserID() > 0 Then LogEvent CurrentUserID(), "EXIT"
    SetTempVar "LoggingOut", True
    Application.Quit acQuitSaveAll
    AppExit = True
End Function

' ---------------------------------------------------------------------
'  Navigation
' ---------------------------------------------------------------------

Public Function CloseForm(ByVal formName As String) As Boolean
    On Error Resume Next
    DoCmd.Close acForm, formName
    CloseForm = True
End Function

Public Function IsFormLoaded(ByVal formName As String) As Boolean
    On Error Resume Next
    IsFormLoaded = CurrentProject.AllForms(formName).IsLoaded
End Function

Public Function OpenAppForm(ByVal formName As String, Optional ByVal whereCond As String = "", Optional ByVal openArgs As String = "") As Boolean
    On Error GoTo Fail
    If CurrentUserID() = 0 Then
        Msg T("err.login_required"), vbExclamation
        Exit Function
    End If
    If (formName = "frmUsers" Or formName = "frmLookups") And Not IsAdmin() Then
        Msg T("msg.no_permission"), vbExclamation
        Exit Function
    End If
    If IsFormLoaded(formName) Then
        If Forms(formName).Dirty Then Forms(formName).Dirty = False
        DoCmd.Close acForm, formName
    End If
    DoCmd.OpenForm formName, acNormal, , whereCond, , acWindowNormal, openArgs
    OpenAppForm = True
    Exit Function
Fail:
    ShowError formName
End Function

' Opens a related form filtered on the current record, e.g. vehicles of a customer.
Public Function OpenChild(ByVal sourceForm As String, ByVal targetForm As String, ByVal keyField As String, Optional ByVal extraField As String = "") As Boolean
    Dim f As Form, keyValue As Variant, args As String
    On Error GoTo Fail
    Set f = Forms(sourceForm)
    If f.Dirty Then f.Dirty = False
    keyValue = f.Controls("c_" & keyField).Value
    If IsNull(keyValue) Or f.NewRecord Then
        Msg T("msg.save_first"), vbExclamation
        Exit Function
    End If
    args = keyField & "=" & keyValue
    If Len(extraField) > 0 Then
        If Not IsNull(f.Controls("c_" & extraField).Value) Then args = args & ";" & extraField & "=" & f.Controls("c_" & extraField).Value
    End If
    OpenChild = OpenAppForm(targetForm, "[" & keyField & "]=" & keyValue, args)
    Exit Function
Fail:
    ShowError "OpenChild"
End Function

' ---------------------------------------------------------------------
'  Generic data forms (header buttons, load/current events)
' ---------------------------------------------------------------------

Public Function HasCtl(ByVal f As Form, ByVal ctlName As String) As Boolean
    Dim c As Control
    On Error Resume Next
    Set c = f.Controls(ctlName)
    HasCtl = (Err.Number = 0)
End Function

' Controls whose Tag is MANAGER / ADMIN / WORKER are shown only to those roles.
Public Sub ApplyRoleTags(ByVal f As Form)
    Dim c As Control
    On Error Resume Next
    For Each c In f.Controls
        Select Case c.Tag
            Case "ADMIN": c.Visible = IsAdmin()
            Case "MANAGER": c.Visible = IsManager()
            Case "WORKER": c.Visible = CanWork()
        End Select
    Next c
End Sub

Public Function DataFormLoad(ByVal formName As String) As Boolean
    Dim f As Form, pairs As Variant, kv As Variant, i As Long
    On Error GoTo Fail
    Set f = Forms(formName)
    ' OpenArgs "Field=Value;Field2=Value2" become default values of new records.
    If Len(Nz(f.OpenArgs, "")) > 0 Then
        pairs = Split(f.OpenArgs, ";")
        For i = LBound(pairs) To UBound(pairs)
            kv = Split(pairs(i), "=")
            If UBound(kv) = 1 Then
                If HasCtl(f, "c_" & kv(0)) Then f.Controls("c_" & kv(0)).DefaultValue = kv(1)
            End If
        Next i
    End If
    ApplyRoleTags f
    DataFormLoad = True
    Exit Function
Fail:
    ShowError formName
End Function

Public Function DataFormCurrent(ByVal formName As String) As Boolean
    Dim f As Form
    On Error GoTo Done
    Set f = Forms(formName)
    If HasCtl(f, "c_VehicleID") And HasCtl(f, "c_CustomerID") Then FilterVehicles f
    If formName = "frmCorrectiveActions" Then ActionsRefreshUI f
    DataFormCurrent = True
Done:
End Function

' Vehicles of the selected customer are listed first (the full list stays, so
' existing rows in the datasheet always show their vehicle).
Private Sub FilterVehicles(ByVal f As Form)
    Dim cust As Long, sql As String
    cust = Nz(f.Controls("c_CustomerID").Value, 0)
    If cust > 0 Then
        sql = SQL_VEH_BASE & " ORDER BY IIf(v.CustomerID=" & cust & ",0,1), v.PlateNumber"
    Else
        sql = SQL_VEH_BASE & " ORDER BY v.PlateNumber"
    End If
    If f.Controls("c_VehicleID").RowSource <> sql Then f.Controls("c_VehicleID").RowSource = sql
End Sub

' After choosing a vehicle, fill in its owner when the customer is still empty.
Public Function VehiclePicked(ByVal formName As String) As Boolean
    Dim f As Form, v As Variant
    On Error Resume Next
    Set f = Forms(formName)
    v = f.Controls("c_VehicleID").Value
    If IsNull(v) Or Not HasCtl(f, "c_CustomerID") Then Exit Function
    If IsNull(f.Controls("c_CustomerID").Value) Then
        f.Controls("c_CustomerID").Value = DLookup("CustomerID", "tblVehicles", "VehicleID=" & v)
        FilterVehicles f
    End If
    VehiclePicked = True
End Function

' After choosing a complaint (tasks form), fill in its customer.
Public Function ComplaintPicked(ByVal formName As String) As Boolean
    Dim f As Form, v As Variant
    On Error Resume Next
    Set f = Forms(formName)
    v = f.Controls("c_ComplaintID").Value
    If IsNull(v) Or Not HasCtl(f, "c_CustomerID") Then Exit Function
    If IsNull(f.Controls("c_CustomerID").Value) Then f.Controls("c_CustomerID").Value = DLookup("CustomerID", "tblComplaints", "ComplaintID=" & v)
    ComplaintPicked = True
End Function

' Header buttons of every data form: find, all, new, save, delete, close.
Public Function FormCmd(ByVal formName As String, ByVal cmd As String) As Boolean
    Dim f As Form
    On Error GoTo Fail
    Set f = Forms(formName)
    Select Case cmd
        Case "find"
            DoFind f
        Case "all"
            f.Controls("txtFind").Value = Null
            f.Filter = ""
            f.FilterOn = False
        Case "new"
            If f.Dirty Then f.Dirty = False
            DoCmd.GoToRecord acDataForm, formName, acNewRec
        Case "save"
            If f.Dirty Then
                f.Dirty = False
                Msg T("msg.saved"), vbInformation
            End If
        Case "delete"
            DoDelete f, formName
        Case "close"
            If f.Dirty Then f.Dirty = False
            DoCmd.Close acForm, formName
    End Select
    FormCmd = True
    Exit Function
Fail:
    ShowError formName
End Function

' The form Tag lists the searchable fields, e.g. "#CustomerID;FullName;@CUST".
'   #Field  numeric match     @CUST  customer name/mobile     @VEH  plate/VIN
Private Sub DoFind(ByVal f As Form)
    Dim s As String, pat As String, parts As String, tokens As Variant, tok As String, i As Long
    s = Trim$(NormText(Nz(f.Controls("txtFind").Value, "")))
    If Len(s) = 0 Then
        f.FilterOn = False
        Exit Sub
    End If
    pat = "'*" & LikeEscape(s) & "*'"
    tokens = Split(f.Tag, ";")
    For i = LBound(tokens) To UBound(tokens)
        tok = Trim$(tokens(i))
        If tok = "@CUST" Then
            AddOr parts, "[CustomerID] IN (SELECT CustomerID FROM tblCustomers WHERE FullName Like " & pat & " OR Mobile Like " & pat & " OR NationalCode Like " & pat & ")"
        ElseIf tok = "@VEH" Then
            AddOr parts, "[VehicleID] IN (SELECT VehicleID FROM tblVehicles WHERE PlateNumber Like " & pat & " OR VIN Like " & pat & ")"
        ElseIf Left$(tok, 1) = "#" Then
            If IsNumeric(s) And Len(s) <= 9 And InStr(s, ".") = 0 And InStr(s, ",") = 0 Then AddOr parts, "[" & Mid$(tok, 2) & "]=" & CLng(s)
        ElseIf Len(tok) > 0 Then
            AddOr parts, "[" & tok & "] Like " & pat
        End If
    Next i
    If Len(parts) = 0 Then Exit Sub
    f.Filter = parts
    f.FilterOn = True
    If f.RecordsetClone.RecordCount = 0 Then Msg T("msg.not_found"), vbInformation
End Sub

Private Sub AddOr(ByRef parts As String, ByVal expr As String)
    If Len(parts) > 0 Then parts = parts & " OR "
    parts = parts & "(" & expr & ")"
End Sub

Private Function LikeEscape(ByVal s As String) As String
    s = Replace(s, "[", "[[]")
    s = Replace(s, "*", "[*]")
    s = Replace(s, "?", "[?]")
    s = Replace(s, "#", "[#]")
    s = Replace(s, "'", "''")
    LikeEscape = s
End Function

Private Sub DoDelete(ByVal f As Form, ByVal formName As String)
    Dim rs As DAO.Recordset
    If Not IsManager() Then
        Msg T("msg.no_permission"), vbExclamation
        Exit Sub
    End If
    If formName = "frmUsers" Then
        Msg T("msg.user_no_delete"), vbExclamation
        Exit Sub
    End If
    If f.NewRecord Then
        f.Undo
        Exit Sub
    End If
    If Not Confirm(T("msg.confirm_delete")) Then Exit Sub
    If f.Dirty Then f.Undo
    Set rs = f.RecordsetClone
    rs.Bookmark = f.Bookmark
    On Error GoTo DelErr
    rs.Delete
    LogEvent CurrentUserID(), "DELETE", formName
    f.Requery
    Exit Sub
DelErr:
    If Err.Number = 3200 Then
        Msg T("msg.delete_related"), vbExclamation
    Else
        ShowError "Delete"
    End If
End Sub

' ---------------------------------------------------------------------
'  Digits and text normalisation (Persian keyboard -> searchable data)
' ---------------------------------------------------------------------

Public Function NormDigits(ByVal s As String) As String
    Dim i As Long
    For i = 0 To 9
        s = Replace(s, ChrW(&H6F0 + i), CStr(i))   ' Persian digits
        s = Replace(s, ChrW(&H660 + i), CStr(i))   ' Arabic digits
    Next i
    NormDigits = s
End Function

Public Function NormText(ByVal s As String) As String
    s = NormDigits(s)
    s = Replace(s, ChrW(&H64A), ChrW(&H6CC))   ' Arabic Yeh -> Persian Yeh
    s = Replace(s, ChrW(&H643), ChrW(&H6A9))   ' Arabic Kaf -> Persian Kaf
    NormText = s
End Function

' AfterUpdate of text boxes: normalise digits and give a soft format warning.
Public Function NormField(ByVal formName As String, ByVal ctlName As String, ByVal rule As String) As Boolean
    Dim c As Control, s As String
    On Error GoTo Done
    Set c = Forms(formName).Controls(ctlName)
    If IsNull(c.Value) Then Exit Function
    s = Trim$(NormText(CStr(c.Value)))
    If rule = "mobile" Or rule = "ncode" Or rule = "digits" Then s = Replace(Replace(s, " ", ""), "-", "")
    If rule = "upper" Then s = UCase$(Replace(s, " ", ""))
    If s <> c.Value Then c.Value = s
    Select Case rule
        Case "mobile"
            If Not (s Like "09#########") Then Msg T("val.mobile"), vbExclamation
        Case "ncode"
            If Not IsValidNationalCode(s) Then Msg T("val.ncode"), vbExclamation
    End Select
    NormField = True
Done:
End Function

Public Function IsValidNationalCode(ByVal s As String) As Boolean
    Dim i As Long, sum As Long, chk As Long, r As Long
    If Not (s Like "##########") Then Exit Function
    For i = 1 To 9
        sum = sum + CLng(Mid$(s, i, 1)) * (11 - i)
    Next i
    chk = CLng(Right$(s, 1))
    r = sum Mod 11
    If r < 2 Then
        IsValidNationalCode = (chk = r)
    Else
        IsValidNationalCode = (chk = 11 - r)
    End If
End Function

' ---------------------------------------------------------------------
'  Main menu and dashboard
' ---------------------------------------------------------------------

Public Function MainOnLoad() As Boolean
    Dim f As Form
    On Error GoTo Fail
    Set f = Forms("frmMain")
    If CurrentUserID() = 0 Then
        Msg T("err.login_required"), vbExclamation
        Exit Function
    End If
    f.Controls("lblUser").Caption = TF("lbl.user_line", Nz(TempVars("UserFullName"), ""), LK("Role", CurrentRole()))
    f.Controls("lblToday").Caption = JDateLong(Date)
    ApplyRoleTags f
    MainOnLoad = True
    Exit Function
Fail:
    ShowError "MainOnLoad"
End Function

Public Function MainRefresh() As Boolean
    On Error Resume Next
    Forms("frmMain").Recalc
    MainRefresh = True
End Function

Public Function MainClosed() As Boolean
    ' Closing the main menu with the window X button ends the program.
    On Error Resume Next
    If Not Nz(TempVars("LoggingOut"), False) Then
        SetTempVar "LoggingOut", True
        Application.Quit acQuitSaveAll
    End If
    MainClosed = True
End Function

Private Function DashWhere(ByVal key As String) As String
    Select Case key
        Case "OPEN": DashWhere = "StatusCode<>'CLOSED'"
        Case "OVERDUE": DashWhere = "StatusCode<>'CLOSED' AND DueAt<Date()"
        Case "PENDING": DashWhere = "PlanStatus='PENDING' OR ResultStatus='PENDING'"
        Case "FOLLOWUP": DashWhere = "FollowUpDone=False AND FollowUpAt<Date()+1"
        Case "MYTASKS": DashWhere = "AssignedTo=" & CurrentUserID() & " AND StatusCode NOT IN ('DONE','CANCELLED')"
        Case "LETTERS": DashWhere = "StatusCode NOT IN ('ANSWERED','ARCHIVED')"
    End Select
End Function

Private Function DashForm(ByVal key As String) As String
    Select Case key
        Case "OPEN", "OVERDUE": DashForm = "frmComplaints"
        Case "PENDING": DashForm = "frmCorrectiveActions"
        Case "FOLLOWUP": DashForm = "frmCRM"
        Case "MYTASKS": DashForm = "frmTasks"
        Case "LETTERS": DashForm = "frmLetters"
    End Select
End Function

Private Function DashTable(ByVal key As String) As String
    Select Case DashForm(key)
        Case "frmComplaints": DashTable = "tblComplaints"
        Case "frmCorrectiveActions": DashTable = "tblCorrectiveActions"
        Case "frmCRM": DashTable = "tblCRMInteractions"
        Case "frmTasks": DashTable = "tblTasks"
        Case "frmLetters": DashTable = "tblLetters"
    End Select
End Function

Public Function DashCount(ByVal key As String) As Long
    On Error Resume Next
    If CurrentUserID() = 0 Then Exit Function
    DashCount = DCount("*", DashTable(key), DashWhere(key))
End Function

Public Function DashOpen(ByVal key As String) As Boolean
    DashOpen = OpenAppForm(DashForm(key), DashWhere(key))
End Function

' ---------------------------------------------------------------------
'  Admin tools: backups and back-end location
' ---------------------------------------------------------------------

Private Sub DailyBackup()
    On Error Resume Next
    If GetAppSetting("LastBackupDay") <> Format$(Date, "yyyymmdd") Then BackupBackend True
End Sub

Public Function BackupBackend(Optional ByVal silent As Boolean = False) As Boolean
    Dim fso As Object, src As String, bkDir As String, dst As String
    On Error GoTo Fail
    src = BackendPath()
    Set fso = CreateObject("Scripting.FileSystemObject")
    bkDir = fso.BuildPath(fso.GetParentFolderName(src), "Backups")
    If Not fso.FolderExists(bkDir) Then fso.CreateFolder bkDir
    dst = fso.BuildPath(bkDir, fso.GetBaseName(src) & "_" & Format$(Now(), "yyyymmdd_hhnnss") & ".accdb")
    fso.CopyFile src, dst, False
    SetAppSetting "LastBackupDay", Format$(Date, "yyyymmdd")
    PruneBackups bkDir, fso.GetBaseName(src), 30
    If Not silent Then Msg TF("msg.backup_done", dst), vbInformation
    BackupBackend = True
    Exit Function
Fail:
    If Not silent Then ShowError "Backup"
End Function

Private Sub PruneBackups(ByVal bkDir As String, ByVal baseName As String, ByVal keep As Long)
    Dim fso As Object, fl As Object, n As Long, oldest As String
    On Error Resume Next
    Set fso = CreateObject("Scripting.FileSystemObject")
    Do
        n = 0: oldest = ""
        For Each fl In fso.GetFolder(bkDir).Files
            If LCase$(Left$(fl.Name, Len(baseName) + 1)) = LCase$(baseName & "_") Then
                n = n + 1
                If Len(oldest) = 0 Or fl.Name < oldest Then oldest = fl.Name
            End If
        Next fl
        If n <= keep Or Len(oldest) = 0 Then Exit Do
        fso.DeleteFile fso.BuildPath(bkDir, oldest), True
        If Err.Number <> 0 Then Exit Do
    Loop
End Sub

Public Function AdminBackup() As Boolean
    If Not IsAdmin() Then Msg T("msg.no_permission"), vbExclamation: Exit Function
    AdminBackup = BackupBackend(False)
End Function

Public Function AdminRelink() As Boolean
    Dim p As String
    If Not IsAdmin() Then Msg T("msg.no_permission"), vbExclamation: Exit Function
    Msg TF("msg.current_be", BackendPath()), vbInformation
    p = PickFile(T("dlg.pick_be"), "Access", "*.accdb", BackendPath())
    If Len(p) = 0 Then Exit Function
    If RelinkAll(p) Then
        If BackendReachable() Then
            Msg TF("msg.relink_ok", p), vbInformation
            MainRefresh
            AdminRelink = True
        End If
    End If
End Function

' ---------------------------------------------------------------------
'  Reports
' ---------------------------------------------------------------------

Public Function ReportOpen(ByVal queryName As String) As Boolean
    On Error GoTo Fail
    DoCmd.OpenQuery queryName, acViewNormal, acReadOnly
    ReportOpen = True
    Exit Function
Fail:
    ShowError queryName
End Function

Public Function ReportExport(ByVal queryName As String) As Boolean
    Dim fso As Object, folder As String, p As String
    On Error GoTo Fail
    Set fso = CreateObject("Scripting.FileSystemObject")
    folder = fso.BuildPath(CreateObject("WScript.Shell").SpecialFolders("MyDocuments"), "SaipaMashayekh_Reports")
    If Not fso.FolderExists(folder) Then fso.CreateFolder folder
    p = fso.BuildPath(folder, Mid$(queryName, 7) & "_" & Format$(Now(), "yyyymmdd_hhnnss") & ".xlsx")
    DoCmd.TransferSpreadsheet acExport, acSpreadsheetTypeExcel12Xml, queryName, p, True
    Application.FollowHyperlink p
    ReportExport = True
    Exit Function
Fail:
    ShowError queryName
End Function

' ---------------------------------------------------------------------
'  Jalali (Persian solar) calendar
' ---------------------------------------------------------------------

Public Sub GregToJalali(ByVal gy As Long, ByVal gm As Long, ByVal gd As Long, ByRef jy As Long, ByRef jm As Long, ByRef jd As Long)
    Dim gdm As Variant, gy2 As Long, days As Long
    gdm = Array(0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)
    If gm > 2 Then gy2 = gy + 1 Else gy2 = gy
    days = 355666 + (365 * gy) + ((gy2 + 3) \ 4) - ((gy2 + 99) \ 100) + ((gy2 + 399) \ 400) + gd + gdm(gm - 1)
    jy = -1595 + (33 * (days \ 12053))
    days = days Mod 12053
    jy = jy + (4 * (days \ 1461))
    days = days Mod 1461
    If days > 365 Then
        jy = jy + ((days - 1) \ 365)
        days = (days - 1) Mod 365
    End If
    If days < 186 Then
        jm = 1 + (days \ 31)
        jd = 1 + (days Mod 31)
    Else
        jm = 7 + ((days - 186) \ 30)
        jd = 1 + ((days - 186) Mod 30)
    End If
End Sub

' "1405/07/21" - sortable, used in forms, queries and exports.
Public Function JDate(ByVal d As Variant) As String
    Dim jy As Long, jm As Long, jd As Long
    If IsNull(d) Or IsEmpty(d) Then Exit Function
    If Not IsDate(d) Then Exit Function
    GregToJalali Year(d), Month(d), Day(d), jy, jm, jd
    JDate = jy & "/" & Format$(jm, "00") & "/" & Format$(jd, "00")
End Function

' Long form with Persian digits, e.g. for the main menu.
Public Function JDateLong(ByVal d As Variant) As String
    Dim jy As Long, jm As Long, jd As Long
    If IsNull(d) Or Not IsDate(d) Then Exit Function
    GregToJalali Year(d), Month(d), Day(d), jy, jm, jd
    JDateLong = FaDigits(T("wd." & Weekday(d, vbSunday)) & " " & jd & " " & T("jm." & jm) & " " & jy)
End Function

Public Function FaDigits(ByVal s As String) As String
    Dim i As Long
    For i = 0 To 9
        s = Replace(s, CStr(i), ChrW(&H6F0 + i))
    Next i
    FaDigits = s
End Function
