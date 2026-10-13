Attribute VB_Name = "modWorkflow"
Option Compare Database
Option Explicit

' =====================================================================
'  Corrective-action workflow and record-level actions.
'
'  Complaint life cycle:
'    NEW -> (plan submitted) PLAN_PENDING -> (manager approves) IN_PROGRESS
'        -> (result submitted) RESULT_PENDING -> (manager approves) CLOSED
'    Any rejection -> NEEDS_REVISION (the plan or result can be resubmitted).
'  Every change is written to tblComplaintHistory and every manager decision
'  to tblApprovals, inside one transaction.
' =====================================================================

Private Const FRM_ACT As String = "frmCorrectiveActions"

' Locks fields and enables buttons on frmCorrectiveActions for the current record.
Public Sub ActionsRefreshUI(ByVal f As Form)
    Dim ps As String, rsl As String, bWork As Boolean, bMgr As Boolean, isNew As Boolean
    On Error Resume Next
    isNew = f.NewRecord
    ps = Nz(f.Controls("c_PlanStatus").Value, "DRAFT")
    rsl = Nz(f.Controls("c_ResultStatus").Value, "NONE")
    bWork = CanWork()
    bMgr = IsManager()
    f.Controls("c_ComplaintID").Locked = Not (isNew Or ps = "DRAFT")
    f.Controls("c_PlanText").Locked = (ps = "PENDING" Or ps = "APPROVED")
    f.Controls("c_ExecutionText").Locked = Not (ps = "APPROVED" And (rsl = "NONE" Or rsl = "REJECTED"))
    f.Controls("cmd_SubmitPlan").Enabled = bWork And (ps = "DRAFT" Or ps = "REJECTED")
    f.Controls("cmd_SubmitResult").Enabled = bWork And ps = "APPROVED" And (rsl = "NONE" Or rsl = "REJECTED")
    f.Controls("cmd_ApprovePlan").Enabled = bMgr And ps = "PENDING" And Not isNew
    f.Controls("cmd_RejectPlan").Enabled = bMgr And ps = "PENDING" And Not isNew
    f.Controls("cmd_ApproveResult").Enabled = bMgr And rsl = "PENDING" And Not isNew
    f.Controls("cmd_RejectResult").Enabled = bMgr And rsl = "PENDING" And Not isNew
End Sub

Public Function WfSubmitPlan() As Boolean
    WfSubmitPlan = SubmitStep("PLAN")
End Function

Public Function WfSubmitResult() As Boolean
    WfSubmitResult = SubmitStep("RESULT")
End Function

Public Function WfApprovePlan() As Boolean
    WfApprovePlan = Decide("PLAN", True)
End Function

Public Function WfRejectPlan() As Boolean
    WfRejectPlan = Decide("PLAN", False)
End Function

Public Function WfApproveResult() As Boolean
    WfApproveResult = Decide("RESULT", True)
End Function

Public Function WfRejectResult() As Boolean
    WfRejectResult = Decide("RESULT", False)
End Function

' Expert submits the plan (phase PLAN) or the execution result (phase RESULT).
Private Function SubmitStep(ByVal phase As String) As Boolean
    Dim ws As DAO.Workspace, db As DAO.Database, inTrans As Boolean
    Dim f As Form, actionID As Long, complaintID As Long, bodyText As String, errDesc As String
    On Error GoTo Fail
    If Not CanWork() Then Msg T("msg.no_permission"), vbExclamation: Exit Function
    Set f = Forms(FRM_ACT)
    If IsNull(f.Controls("c_ComplaintID").Value) Then Msg T("msg.complaint_required"), vbExclamation: Exit Function
    If phase = "PLAN" Then
        bodyText = Trim$(Nz(f.Controls("c_PlanText").Value, ""))
        If Len(bodyText) = 0 Then Msg T("msg.plan_required"), vbExclamation: Exit Function
    Else
        bodyText = Trim$(Nz(f.Controls("c_ExecutionText").Value, ""))
        If Len(bodyText) = 0 Then Msg T("msg.result_required"), vbExclamation: Exit Function
    End If
    If f.Dirty Then f.Dirty = False
    actionID = Nz(f.Controls("c_ActionID").Value, 0)
    complaintID = f.Controls("c_ComplaintID").Value
    If actionID = 0 Then Exit Function
    If Not Confirm(T("msg.confirm_submit")) Then Exit Function

    Set ws = DBEngine.Workspaces(0)
    Set db = CurrentDb
    ws.BeginTrans
    inTrans = True
    If phase = "PLAN" Then
        db.Execute "UPDATE tblCorrectiveActions SET PlanStatus='PENDING', PlannedAt=Now(), CreatedBy=IIf(CreatedBy Is Null," & CurrentUserID() & ",CreatedBy) " & _
                   "WHERE ActionID=" & actionID & " AND PlanStatus IN ('DRAFT','REJECTED')", dbFailOnError
        If db.RecordsAffected <> 1 Then Err.Raise vbObjectError + 610, , T("msg.state_changed")
        ChangeComplaintStatus db, complaintID, "PLAN_PENDING", actionID, T("ev.plan_submitted"), bodyText
    Else
        db.Execute "UPDATE tblCorrectiveActions SET ResultStatus='PENDING', ExecutedAt=Now(), ExecutedBy=" & CurrentUserID() & " " & _
                   "WHERE ActionID=" & actionID & " AND PlanStatus='APPROVED' AND ResultStatus IN ('NONE','REJECTED')", dbFailOnError
        If db.RecordsAffected <> 1 Then Err.Raise vbObjectError + 611, , T("msg.state_changed")
        ChangeComplaintStatus db, complaintID, "RESULT_PENDING", actionID, T("ev.result_submitted"), bodyText
    End If
    ws.CommitTrans
    inTrans = False
    f.Refresh
    ActionsRefreshUI f
    Msg T("msg.sent_for_approval"), vbInformation
    SubmitStep = True
    Exit Function
Fail:
    errDesc = Err.Description
    On Error Resume Next
    If inTrans Then ws.Rollback
    Msg T("err.prefix") & vbCrLf & errDesc, vbExclamation
End Function

' Manager decision on a plan or a result. Rejection requires a reason.
Private Function Decide(ByVal phase As String, ByVal approved As Boolean) As Boolean
    Dim ws As DAO.Workspace, db As DAO.Database, rs As DAO.Recordset, logRs As DAO.Recordset, inTrans As Boolean
    Dim f As Form, actionID As Long, complaintID As Long, answer As Variant, comments As String
    Dim newStatus As String, nextComplaint As String, errDesc As String
    On Error GoTo Fail
    If Not IsManager() Then Msg T("msg.no_permission"), vbExclamation: Exit Function
    Set f = Forms(FRM_ACT)
    If f.Dirty Then f.Dirty = False
    actionID = Nz(f.Controls("c_ActionID").Value, 0)
    If actionID = 0 Then Exit Function

    If approved Then
        answer = AskText(T("prm.approve_comment"))
    Else
        answer = AskText(T("prm.reject_reason"))
    End If
    If IsNull(answer) Then Exit Function
    comments = Trim$(answer)
    If Not approved And Len(comments) = 0 Then Msg T("msg.reason_required"), vbExclamation: Exit Function
    If Len(comments) = 0 Then comments = T("lbl.no_comment")
    If approved Then newStatus = "APPROVED" Else newStatus = "REJECTED"

    Set ws = DBEngine.Workspaces(0)
    Set db = CurrentDb
    ws.BeginTrans
    inTrans = True
    Set rs = db.OpenRecordset("SELECT * FROM tblCorrectiveActions WHERE ActionID=" & actionID, dbOpenDynaset)
    If rs.EOF Then Err.Raise vbObjectError + 620, , T("msg.action_not_found")
    complaintID = rs!ComplaintID
    If phase = "PLAN" Then
        If Nz(rs!PlanStatus, "") <> "PENDING" Then Err.Raise vbObjectError + 621, , T("msg.plan_not_pending")
        If approved Then nextComplaint = "IN_PROGRESS" Else nextComplaint = "NEEDS_REVISION"
        rs.Edit
        rs!PlanStatus = newStatus
        rs!PlanApprovedBy = CurrentUserID()
        rs!PlanApprovedAt = Now()
        rs.Update
    ElseIf phase = "RESULT" Then
        If Nz(rs!PlanStatus, "") <> "APPROVED" Then Err.Raise vbObjectError + 622, , T("msg.plan_not_approved")
        If Nz(rs!ResultStatus, "") <> "PENDING" Then Err.Raise vbObjectError + 623, , T("msg.result_not_pending")
        If approved Then nextComplaint = "CLOSED" Else nextComplaint = "NEEDS_REVISION"
        rs.Edit
        rs!ResultStatus = newStatus
        rs!ResultApprovedBy = CurrentUserID()
        rs!ResultApprovedAt = Now()
        rs.Update
    Else
        Err.Raise vbObjectError + 624, , "Invalid phase: " & phase
    End If
    rs.Close

    Set logRs = db.OpenRecordset("SELECT * FROM tblApprovals WHERE 1=0", dbOpenDynaset)
    logRs.AddNew
    logRs!ActionID = actionID
    logRs!PhaseCode = phase
    logRs!DecisionCode = newStatus
    logRs!CommentsText = comments
    logRs!DecidedBy = CurrentUserID()
    logRs!DecidedAt = Now()
    logRs.Update
    logRs.Close

    ChangeComplaintStatus db, complaintID, nextComplaint, actionID, _
        T("ev.decision") & " - " & T("lbl.phase_" & LCase$(phase)) & ": " & LK("PlanStatus", newStatus), comments
    ws.CommitTrans
    inTrans = False
    f.Refresh
    ActionsRefreshUI f
    Msg T("msg.decision_saved"), vbInformation
    Decide = True
    Exit Function
Fail:
    errDesc = Err.Description
    On Error Resume Next
    If inTrans Then ws.Rollback
    Msg T("err.prefix") & vbCrLf & errDesc, vbExclamation
End Function

Public Sub ChangeComplaintStatus(ByVal db As DAO.Database, ByVal complaintID As Long, ByVal newStatus As String, ByVal actionID As Long, ByVal eventText As String, ByVal details As String)
    Dim rs As DAO.Recordset, oldStatus As String
    Set rs = db.OpenRecordset("SELECT ComplaintID, StatusCode, ClosedAt FROM tblComplaints WHERE ComplaintID=" & complaintID, dbOpenDynaset)
    If rs.EOF Then Err.Raise vbObjectError + 630, , T("msg.complaint_not_found")
    oldStatus = Nz(rs!StatusCode, "")
    rs.Edit
    rs!StatusCode = newStatus
    If newStatus = "CLOSED" Then
        rs!ClosedAt = Now()
    Else
        rs!ClosedAt = Null
    End If
    rs.Update
    rs.Close
    WriteComplaintHistory db, complaintID, actionID, eventText, LK("ComplaintStatus", oldStatus), LK("ComplaintStatus", newStatus), details
End Sub

Public Sub WriteComplaintHistory(ByVal db As DAO.Database, ByVal complaintID As Long, ByVal actionID As Long, ByVal eventText As String, ByVal oldValue As String, ByVal newValue As String, ByVal details As String)
    Dim rs As DAO.Recordset
    Set rs = db.OpenRecordset("SELECT * FROM tblComplaintHistory WHERE 1=0", dbOpenDynaset)
    rs.AddNew
    rs!ComplaintID = complaintID
    If actionID > 0 Then rs!ActionID = actionID
    rs!EventText = Left$(eventText, 150)
    rs!OldValue = oldValue
    rs!NewValue = newValue
    If Len(details) > 0 Then rs!DetailsText = details
    rs!ActorUserID = CurrentUserID()
    rs!EventAt = Now()
    rs.Update
    rs.Close
End Sub

' Manager closes a complaint directly (e.g. no corrective action needed).
Public Function WfCloseComplaint() As Boolean
    Dim ws As DAO.Workspace, db As DAO.Database, inTrans As Boolean, f As Form
    Dim complaintID As Long, answer As Variant, errDesc As String
    On Error GoTo Fail
    If Not IsManager() Then Msg T("msg.no_permission"), vbExclamation: Exit Function
    Set f = Forms("frmComplaints")
    If f.Dirty Then f.Dirty = False
    complaintID = Nz(f.Controls("c_ComplaintID").Value, 0)
    If complaintID = 0 Then Msg T("msg.save_first"), vbExclamation: Exit Function
    If Nz(f.Controls("c_StatusCode").Value, "") = "CLOSED" Then Msg T("msg.already_closed"), vbInformation: Exit Function
    If DCount("*", "tblCorrectiveActions", "ComplaintID=" & complaintID & " AND (PlanStatus='PENDING' OR ResultStatus='PENDING')") > 0 Then
        If Not Confirm(T("msg.close_with_pending")) Then Exit Function
    End If
    answer = AskText(T("prm.close_comment"))
    If IsNull(answer) Then Exit Function
    Set ws = DBEngine.Workspaces(0)
    Set db = CurrentDb
    ws.BeginTrans
    inTrans = True
    ChangeComplaintStatus db, complaintID, "CLOSED", 0, T("ev.closed_by_manager"), Trim$(answer)
    ws.CommitTrans
    inTrans = False
    f.Refresh
    Msg T("msg.complaint_closed"), vbInformation
    WfCloseComplaint = True
    Exit Function
Fail:
    errDesc = Err.Description
    On Error Resume Next
    If inTrans Then ws.Rollback
    Msg T("err.prefix") & vbCrLf & errDesc, vbExclamation
End Function

Public Function OpenComplaintHistory() As Boolean
    Dim id As Long
    On Error Resume Next
    id = Nz(Forms("frmComplaints").Controls("c_ComplaintID").Value, 0)
    If id = 0 Then Msg T("msg.save_first"), vbExclamation: Exit Function
    OpenComplaintHistory = OpenAppForm("frmComplaintHistory", "ComplaintID=" & id)
End Function

' ---------------------------------------------------------------------
'  CRM, tasks, services, letters
' ---------------------------------------------------------------------

Public Function CrmFollowUpDone() As Boolean
    Dim f As Form
    On Error GoTo Fail
    Set f = Forms("frmCRM")
    If f.NewRecord Then Exit Function
    f.Controls("c_FollowUpDone").Value = True
    f.Dirty = False
    Msg T("msg.saved"), vbInformation
    CrmFollowUpDone = True
    Exit Function
Fail:
    ShowError "CRM"
End Function

Public Function TaskDone() As Boolean
    Dim f As Form
    On Error GoTo Fail
    Set f = Forms("frmTasks")
    If f.NewRecord Then Exit Function
    f.Controls("c_StatusCode").Value = "DONE"
    f.Controls("c_CompletedAt").Value = Now()
    f.Dirty = False
    Msg T("msg.saved"), vbInformation
    TaskDone = True
    Exit Function
Fail:
    ShowError "Task"
End Function

' Form AfterUpdate of frmServices: keep the vehicle odometer up to date.
Public Function ServiceSaved() As Boolean
    Dim f As Form, v As Variant, m As Variant
    On Error Resume Next
    Set f = Forms("frmServices")
    v = f.Controls("c_VehicleID").Value
    m = f.Controls("c_Mileage").Value
    If IsNull(v) Or IsNull(m) Then Exit Function
    CurrentDb.Execute "UPDATE tblVehicles SET Odometer=" & CLng(m) & " WHERE VehicleID=" & CLng(v) & " AND (Odometer Is Null OR Odometer<" & CLng(m) & ")"
    ServiceSaved = True
End Function

Public Function LetterStatusChanged() As Boolean
    Dim f As Form, id As Long
    On Error GoTo Fail
    Set f = Forms("frmLetters")
    If f.Dirty Then f.Dirty = False
    id = Nz(f.Controls("c_LetterID").Value, 0)
    If id = 0 Then Exit Function
    WriteLetterHistory id, T("ev.letter_status"), LK("LetterStatus", f.Controls("c_StatusCode").Value)
    LetterStatusChanged = True
    Exit Function
Fail:
    ShowError "Letter"
End Function

Private Sub WriteLetterHistory(ByVal letterID As Long, ByVal eventText As String, ByVal details As String)
    Dim rs As DAO.Recordset
    Set rs = CurrentDb.OpenRecordset("SELECT * FROM tblLetterHistory WHERE 1=0", dbOpenDynaset)
    rs.AddNew
    rs!LetterID = letterID
    rs!EventText = Left$(eventText, 150)
    rs!DetailsText = details
    rs!ActorUserID = CurrentUserID()
    rs!EventAt = Now()
    rs.Update
    rs.Close
End Sub

' Copies the chosen file next to the data file (Attachments folder) so that
' every computer on the network can open it.
Public Function LetterAttach() As Boolean
    Dim f As Form, id As Long, src As String, fso As Object, attDir As String, dst As String
    On Error GoTo Fail
    Set f = Forms("frmLetters")
    If f.Dirty Then f.Dirty = False
    id = Nz(f.Controls("c_LetterID").Value, 0)
    If id = 0 Then Msg T("msg.save_first"), vbExclamation: Exit Function
    src = PickFile(T("dlg.pick_attachment"), "*", "*.*")
    If Len(src) = 0 Then Exit Function
    Set fso = CreateObject("Scripting.FileSystemObject")
    attDir = fso.BuildPath(fso.GetParentFolderName(BackendPath()), "Attachments")
    If Not fso.FolderExists(attDir) Then fso.CreateFolder attDir
    dst = fso.BuildPath(attDir, "L" & id & "_" & Format$(Now(), "yyyymmddhhnnss") & "_" & fso.GetFileName(src))
    fso.CopyFile src, dst, False
    f.Controls("c_AttachmentPath").Value = dst
    f.Dirty = False
    WriteLetterHistory id, T("ev.letter_attached"), fso.GetFileName(src)
    Msg T("msg.attached"), vbInformation
    LetterAttach = True
    Exit Function
Fail:
    ShowError "Attach"
End Function

Public Function LetterOpenAttachment() As Boolean
    Dim p As String
    On Error GoTo Fail
    p = Nz(Forms("frmLetters").Controls("c_AttachmentPath").Value, "")
    If Len(p) = 0 Then Msg T("msg.no_attachment"), vbInformation: Exit Function
    If Len(Dir$(p)) = 0 Then Msg TF("msg.file_missing", p), vbExclamation: Exit Function
    Application.FollowHyperlink p
    LetterOpenAttachment = True
    Exit Function
Fail:
    ShowError "Attachment"
End Function

Public Function OpenLetterHistory() As Boolean
    Dim id As Long
    On Error Resume Next
    id = Nz(Forms("frmLetters").Controls("c_LetterID").Value, 0)
    If id = 0 Then Msg T("msg.save_first"), vbExclamation: Exit Function
    OpenLetterHistory = OpenAppForm("frmLetterHistory", "LetterID=" & id)
End Function

' ---------------------------------------------------------------------
'  Users (admin only)
' ---------------------------------------------------------------------

Public Function UserSetPassword() As Boolean
    Dim f As Form, id As Long, pwd As Variant, salt As String
    On Error GoTo Fail
    If Not IsAdmin() Then Msg T("msg.no_permission"), vbExclamation: Exit Function
    Set f = Forms("frmUsers")
    If f.Dirty Then f.Dirty = False
    id = Nz(f.Controls("c_UserID").Value, 0)
    If id = 0 Then Msg T("msg.save_first"), vbExclamation: Exit Function
    pwd = AskText(TF("prm.new_password", f.Controls("c_FullName").Value), "", True)
    If IsNull(pwd) Then Exit Function
    If Len(pwd) < MIN_PASSWORD_LEN Then Msg TF("msg.pwd_short", MIN_PASSWORD_LEN), vbExclamation: Exit Function
    salt = NewSalt()
    CurrentDb.Execute "UPDATE tblUsers SET PwdSalt=" & SqlStr(salt) & ", PwdHash=" & SqlStr(HashPassword(CStr(pwd), salt)) & _
                      ", MustChangePwd=True, FailedLogins=0 WHERE UserID=" & id, dbFailOnError
    LogEvent CurrentUserID(), "PWD_RESET", CStr(id)
    f.Refresh
    Msg T("msg.pwd_set"), vbInformation
    UserSetPassword = True
    Exit Function
Fail:
    ShowError "Password"
End Function
