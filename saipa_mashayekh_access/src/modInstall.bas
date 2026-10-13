Attribute VB_Name = "modInstall"
Option Compare Database
Option Explicit

' =====================================================================
'  Builds the whole application inside the current front-end database:
'  UI texts, back-end data file (created only when missing - existing data
'  is never deleted), tables/indexes/relations, seed data, links, queries,
'  forms and start-up options.
'
'  Setup.vbs calls it automatically. Manual use (Immediate window):
'     ? Mashayekh_Install("D:\Mashayekh\Data\SaipaMashayekh_Data.accdb", "D:\Setup\src\ui_fa.txt")
' =====================================================================

Private Const FORM_W As Long = 12000
Private Const UI_FONT As String = "Tahoma"

' Data-form layout (twips): label on the right, input on the left.
Private Const LBL_X As Long = 9350
Private Const LBL_W As Long = 2350
Private Const IN_X As Long = 300
Private Const IN_W As Long = 8900
Private Const DATE_X As Long = 5800
Private Const DATE_W As Long = 3400
Private Const J_W As Long = 5350

Private mStep As String
Private mWarnings As String
Private mFN As String              ' temporary name of the form being built
Private mLookupSeed As Collection  ' "Category|Code|Title" in file order

Private Const CLR_HEAD As Long = 6634518   ' RGB(22, 60, 101)
Private Const CLR_BODY As Long = 16381684   ' RGB(244, 246, 249)
Private Const CLR_TITLE As Long = 6634518   ' RGB(22, 60, 101)
Private Const CLR_WHITE As Long = 16777215   ' RGB(255, 255, 255)
Private Const CLR_LOCK As Long = 15854824   ' RGB(232, 236, 241)
Private Const CLR_MUTED As Long = 8878190   ' RGB(110, 120, 135)
Private Const CLR_TILE As Long = 16777215   ' RGB(255, 255, 255)
Private Const CLR_ACCENT As Long = 2957000   ' RGB(200, 30, 45)

Public Function Mashayekh_Install(ByVal bePath As String, ByVal resPath As String) As String
    Dim be As DAO.Database
    On Error GoTo Fail
    mWarnings = ""
    mStep = "texts"
    LoadUIText resPath
    mStep = "backend"
    If Len(Dir$(bePath)) = 0 Then
        Set be = DBEngine.CreateDatabase(bePath, dbLangGeneral)
    Else
        Set be = DBEngine.OpenDatabase(bePath)
    End If
    mStep = "schema"
    EnsureSchema be
    mStep = "seed"
    SeedData be
    be.Close
    Set be = Nothing
    mStep = "link"
    LinkBackend bePath
    ResetCaches
    mStep = "queries"
    BuildQueries
    mStep = "forms"
    BuildAllForms
    mStep = "startup"
    SetStartupProps
    Mashayekh_Install = "OK" & mWarnings
    Exit Function
Fail:
    Mashayekh_Install = "ERROR [" & mStep & IIf(Len(mFN) > 0 And mStep = "forms", "/" & mFN, "") & "] " & Err.Number & ": " & Err.Description
End Function

' ---------------------------------------------------------------------
'  UI texts (UTF-8 file -> local table tblUIText)
' ---------------------------------------------------------------------

Private Sub LoadUIText(ByVal resPath As String)
    Dim db As DAO.Database, td As DAO.TableDef, fld As DAO.Field, idx As DAO.Index
    Dim st As Object, fileText As String, lines As Variant, i As Long, ln As String, p As Long
    Dim k As String, v As String, rs As DAO.Recordset, seen As Object, parts As Variant
    Set db = CurrentDb
    If Not TableExistsIn(db, "tblUIText") Then
        Set td = db.CreateTableDef("tblUIText")
        td.Fields.Append td.CreateField("TextKey", dbText, 100)
        Set fld = td.CreateField("TextValue", dbMemo)
        td.Fields.Append fld
        Set idx = td.CreateIndex("PrimaryKey")
        idx.Primary = True
        idx.Unique = True
        idx.Fields.Append idx.CreateField("TextKey")
        td.Indexes.Append idx
        db.TableDefs.Append td
    End If
    db.Execute "DELETE FROM tblUIText", dbFailOnError

    Set st = CreateObject("ADODB.Stream")
    st.Type = 2
    st.Charset = "utf-8"
    st.Open
    st.LoadFromFile resPath
    fileText = st.ReadText(-1)
    st.Close
    fileText = Replace(fileText, vbCr, "")
    If Len(fileText) > 0 Then
        If AscW(Left$(fileText, 1)) = &HFEFF Then fileText = Mid$(fileText, 2)
    End If

    Set seen = CreateObject("Scripting.Dictionary")
    seen.CompareMode = 1
    Set mLookupSeed = New Collection
    Set rs = db.OpenRecordset("tblUIText", dbOpenDynaset)
    lines = Split(fileText, vbLf)
    For i = LBound(lines) To UBound(lines)
        ln = Trim$(lines(i))
        If Len(ln) > 0 Then
            If Left$(ln, 1) <> "#" Then
                p = InStr(ln, "=")
                If p > 1 Then
                    k = Trim$(Left$(ln, p - 1))
                    v = Replace(Trim$(Mid$(ln, p + 1)), "\n", vbCrLf)
                    If Not seen.Exists(k) Then
                        seen.Add k, True
                        rs.AddNew
                        rs!TextKey = k
                        rs!TextValue = v
                        rs.Update
                        If Left$(k, 3) = "lk." Then
                            parts = Split(k, ".")
                            If UBound(parts) = 2 Then mLookupSeed.Add parts(1) & "|" & parts(2) & "|" & v
                        End If
                    End If
                End If
            End If
        End If
    Next i
    rs.Close
    ResetCaches
End Sub

' ---------------------------------------------------------------------
'  Schema (idempotent: creates what is missing, never drops anything)
'  Field spec: "Name|Type|Size|Flags|Default"
'     Type T=text M=memo N=long D=date B=yes/no C=currency, Flags R=required
' ---------------------------------------------------------------------

Private Sub EnsureSchema(ByVal be As DAO.Database)
    EnsureTable be, "tblUsers", "UserID", Array("FullName|T|100|R", "UserName|T|60|R", "RoleCode|T|20|R|""STAFF""", _
        "PwdHash|T|64", "PwdSalt|T|64", "MustChangePwd|B|||False", "IsActive|B|||True", "FailedLogins|N|||0", _
        "LastLoginAt|D", "CreatedAt|D|||Now()")
    EnsureTable be, "tblLookups", "LookupID", Array("Category|T|30|R", "Code|T|30|R", "TitleFa|T|100|R", "SortOrder|N|||0", "IsActive|B|||True")
    EnsureTable be, "tblSettings", "SettingID", Array("SettingName|T|80|R", "SettingValue|T|255")
    EnsureTable be, "tblCustomers", "CustomerID", Array("FullName|T|120|R", "Mobile|T|20", "Phone|T|20", "NationalCode|T|15", _
        "CityText|T|60", "AddressText|M", "Notes|M", "CreatedAt|D|||Now()", "CreatedBy|N")
    EnsureTable be, "tblVehicles", "VehicleID", Array("CustomerID|N||R", "PlateNumber|T|30", "VIN|T|30", "ModelName|T|80", _
        "ColorText|T|30", "ProductionYear|T|10", "Odometer|N", "SaleDate|D", "WarrantyEnd|D", "Notes|M", "CreatedAt|D|||Now()", "CreatedBy|N")
    EnsureTable be, "tblComplaints", "ComplaintID", Array("CustomerID|N||R", "VehicleID|N", "ChannelCode|T|20", "SubjectText|T|200|R", _
        "ComplaintText|M", "RootCause|M", "StatusCode|T|30|R|""NEW""", "PriorityCode|T|20|R|""NORMAL""", "OwnerUserID|N", _
        "CreatedAt|D|||Now()", "CreatedBy|N", "DueAt|D", "ClosedAt|D", "SatisfactionCode|T|20")
    EnsureTable be, "tblCorrectiveActions", "ActionID", Array("ComplaintID|N||R", "PlanText|M", "PlannedAt|D", _
        "PlanStatus|T|20|R|""DRAFT""", "PlanApprovedBy|N", "PlanApprovedAt|D", "ExecutionText|M", "ExecutedAt|D", "ExecutedBy|N", _
        "ResultStatus|T|20|R|""NONE""", "ResultApprovedBy|N", "ResultApprovedAt|D", "CreatedAt|D|||Now()", "CreatedBy|N")
    EnsureTable be, "tblApprovals", "ApprovalID", Array("ActionID|N||R", "PhaseCode|T|20", "DecisionCode|T|20", "CommentsText|M", _
        "DecidedBy|N", "DecidedAt|D|||Now()")
    EnsureTable be, "tblComplaintHistory", "HistoryID", Array("ComplaintID|N||R", "ActionID|N", "EventText|T|150", "OldValue|M", _
        "NewValue|M", "DetailsText|M", "ActorUserID|N", "EventAt|D|||Now()")
    EnsureTable be, "tblCRMInteractions", "InteractionID", Array("CustomerID|N||R", "VehicleID|N", "UserID|N", "ChannelCode|T|20", _
        "SubjectText|T|150", "DetailText|M", "ContactAt|D|||Now()", "FollowUpAt|D", "FollowUpDone|B|||False", "ResultText|T|120")
    EnsureTable be, "tblTasks", "TaskID", Array("TitleText|T|200|R", "DescriptionText|M", "AssignedTo|N", "CreatedBy|N", "CustomerID|N", _
        "ComplaintID|N", "PriorityCode|T|20||""NORMAL""", "DueAt|D", "StatusCode|T|20|R|""OPEN""", "CreatedAt|D|||Now()", "CompletedAt|D")
    EnsureTable be, "tblLetters", "LetterID", Array("LetterNo|T|50", "DirectionCode|T|20|R|""IN""", "SubjectText|T|200|R", "BodyText|M", _
        "SenderText|T|120", "ReceiverText|T|120", "LetterAt|D|||Date()", "AssignedTo|N", "StatusCode|T|20|R|""NEW""", _
        "AttachmentPath|T|255", "CreatedBy|N", "CreatedAt|D|||Now()")
    EnsureTable be, "tblLetterHistory", "HistoryID", Array("LetterID|N||R", "EventText|T|150", "ActorUserID|N", "DetailsText|M", "EventAt|D|||Now()")
    EnsureTable be, "tblServices", "ServiceID", Array("VehicleID|N||R", "ServiceName|T|100|R", "ServiceAt|D|||Date()", "Mileage|N", _
        "NextMileage|N", "CostAmount|C", "Notes|M", "CreatedBy|N", "CreatedAt|D|||Now()")
    EnsureTable be, "tblAuditLog", "LogID", Array("UserID|N", "EventCode|T|30", "DetailsText|T|255", "MachineName|T|64", "EventAt|D|||Now()")

    EnsureIndex be, "tblUsers", "uxUserName", "UserName", True
    EnsureIndex be, "tblLookups", "uxCategoryCode", "Category;Code", True
    EnsureIndex be, "tblSettings", "uxSettingName", "SettingName", True
    EnsureIndex be, "tblCustomers", "ixFullName", "FullName", False
    EnsureIndex be, "tblCustomers", "ixMobile", "Mobile", False
    EnsureIndex be, "tblCustomers", "ixNationalCode", "NationalCode", False
    EnsureIndex be, "tblVehicles", "ixPlate", "PlateNumber", False
    EnsureIndex be, "tblVehicles", "ixVIN", "VIN", False
    EnsureIndex be, "tblComplaints", "ixStatusDue", "StatusCode;DueAt", False
    EnsureIndex be, "tblCorrectiveActions", "ixPlanStatus", "PlanStatus", False
    EnsureIndex be, "tblCorrectiveActions", "ixResultStatus", "ResultStatus", False
    EnsureIndex be, "tblCRMInteractions", "ixFollowUp", "FollowUpDone;FollowUpAt", False
    EnsureIndex be, "tblTasks", "ixAssignedDue", "AssignedTo;DueAt", False
    EnsureIndex be, "tblTasks", "ixStatus", "StatusCode", False
    EnsureIndex be, "tblLetters", "ixLetterNo", "LetterNo", False
    EnsureIndex be, "tblLetters", "ixStatus", "StatusCode", False
    EnsureIndex be, "tblAuditLog", "ixEventAt", "EventAt", False

    EnsureRelation be, "relVehiclesCustomers", "tblCustomers", "CustomerID", "tblVehicles", "CustomerID"
    EnsureRelation be, "relComplaintsCustomers", "tblCustomers", "CustomerID", "tblComplaints", "CustomerID"
    EnsureRelation be, "relComplaintsVehicles", "tblVehicles", "VehicleID", "tblComplaints", "VehicleID"
    EnsureRelation be, "relComplaintsOwner", "tblUsers", "UserID", "tblComplaints", "OwnerUserID"
    EnsureRelation be, "relActionsComplaints", "tblComplaints", "ComplaintID", "tblCorrectiveActions", "ComplaintID"
    EnsureRelation be, "relApprovalsActions", "tblCorrectiveActions", "ActionID", "tblApprovals", "ActionID"
    EnsureRelation be, "relHistoryComplaints", "tblComplaints", "ComplaintID", "tblComplaintHistory", "ComplaintID"
    EnsureRelation be, "relCRMCustomers", "tblCustomers", "CustomerID", "tblCRMInteractions", "CustomerID"
    EnsureRelation be, "relCRMVehicles", "tblVehicles", "VehicleID", "tblCRMInteractions", "VehicleID"
    EnsureRelation be, "relTasksUsers", "tblUsers", "UserID", "tblTasks", "AssignedTo"
    EnsureRelation be, "relServicesVehicles", "tblVehicles", "VehicleID", "tblServices", "VehicleID"
    EnsureRelation be, "relLetterHistory", "tblLetters", "LetterID", "tblLetterHistory", "LetterID"
End Sub

Private Sub EnsureTable(ByVal be As DAO.Database, ByVal tableName As String, ByVal pkName As String, ByVal fieldSpecs As Variant)
    Dim td As DAO.TableDef, fld As DAO.Field, idx As DAO.Index, s As Variant
    If Not TableExistsIn(be, tableName) Then
        Set td = be.CreateTableDef(tableName)
        Set fld = td.CreateField(pkName, dbLong)
        fld.Attributes = dbAutoIncrField
        td.Fields.Append fld
        For Each s In fieldSpecs
            td.Fields.Append MakeField(td, CStr(s), True)
        Next s
        Set idx = td.CreateIndex("PrimaryKey")
        idx.Primary = True
        idx.Unique = True
        idx.Fields.Append idx.CreateField(pkName)
        td.Indexes.Append idx
        be.TableDefs.Append td
    Else
        Set td = be.TableDefs(tableName)
        For Each s In fieldSpecs
            If Not FieldExistsIn(td, Split(CStr(s), "|")(0)) Then td.Fields.Append MakeField(td, CStr(s), False)
        Next s
    End If
End Sub

Private Function MakeField(ByVal td As DAO.TableDef, ByVal spec As String, ByVal allowRequired As Boolean) As DAO.Field
    Dim p As Variant, fld As DAO.Field, sz As Long
    p = Split(spec & "||||", "|")
    Select Case p(1)
        Case "T"
            sz = 255
            If Len(p(2)) > 0 Then sz = CLng(p(2))
            Set fld = td.CreateField(p(0), dbText, sz)
            fld.AllowZeroLength = False
        Case "M"
            Set fld = td.CreateField(p(0), dbMemo)
        Case "N"
            Set fld = td.CreateField(p(0), dbLong)
        Case "D"
            Set fld = td.CreateField(p(0), dbDate)
        Case "B"
            Set fld = td.CreateField(p(0), dbBoolean)
        Case "C"
            Set fld = td.CreateField(p(0), dbCurrency)
        Case Else
            Err.Raise vbObjectError + 500, , "Unknown field type: " & spec
    End Select
    If allowRequired And InStr(1, p(3), "R", vbBinaryCompare) > 0 Then fld.Required = True
    If Len(p(4)) > 0 Then fld.DefaultValue = p(4)
    Set MakeField = fld
End Function

Private Sub EnsureIndex(ByVal be As DAO.Database, ByVal tableName As String, ByVal indexName As String, ByVal fieldList As String, ByVal isUnique As Boolean)
    Dim td As DAO.TableDef, idx As DAO.Index, f As Variant
    On Error GoTo Fail
    Set td = be.TableDefs(tableName)
    For Each idx In td.Indexes
        If idx.Name = indexName Then Exit Sub
    Next idx
    Set idx = td.CreateIndex(indexName)
    For Each f In Split(fieldList, ";")
        idx.Fields.Append idx.CreateField(CStr(f))
    Next f
    idx.Unique = isUnique
    idx.IgnoreNulls = Not isUnique
    td.Indexes.Append idx
    Exit Sub
Fail:
    mWarnings = mWarnings & vbCrLf & "Index " & tableName & "." & indexName & ": " & Err.Description
End Sub

Private Sub EnsureRelation(ByVal be As DAO.Database, ByVal relName As String, ByVal parentTable As String, ByVal parentField As String, ByVal childTable As String, ByVal childField As String)
    Dim r As DAO.Relation, fld As DAO.Field
    On Error GoTo Fail
    For Each r In be.Relations
        If r.Name = relName Then Exit Sub
    Next r
    Set r = be.CreateRelation(relName, parentTable, childTable, 0)
    Set fld = r.CreateField(parentField)
    fld.ForeignName = childField
    r.Fields.Append fld
    be.Relations.Append r
    Exit Sub
Fail:
    mWarnings = mWarnings & vbCrLf & "Relation " & relName & ": " & Err.Description
End Sub

Private Function TableExistsIn(ByVal db As DAO.Database, ByVal tableName As String) As Boolean
    Dim td As DAO.TableDef
    For Each td In db.TableDefs
        If td.Name = tableName Then
            TableExistsIn = True
            Exit Function
        End If
    Next td
End Function

Private Function FieldExistsIn(ByVal td As DAO.TableDef, ByVal fieldName As String) As Boolean
    Dim fld As DAO.Field
    For Each fld In td.Fields
        If fld.Name = fieldName Then
            FieldExistsIn = True
            Exit Function
        End If
    Next fld
End Function

' ---------------------------------------------------------------------
'  Seed data: lookups, settings, first administrator
' ---------------------------------------------------------------------

Private Sub SeedData(ByVal be As DAO.Database)
    Dim rs As DAO.Recordset, existing As Object, item As Variant, parts As Variant, n As Long, salt As String

    Set existing = CreateObject("Scripting.Dictionary")
    existing.CompareMode = 1
    Set rs = be.OpenRecordset("SELECT Category, Code FROM tblLookups", dbOpenSnapshot)
    Do Until rs.EOF
        existing(rs!Category & "|" & rs!Code) = True
        rs.MoveNext
    Loop
    rs.Close
    Set rs = be.OpenRecordset("tblLookups", dbOpenDynaset)
    For Each item In mLookupSeed
        parts = Split(item, "|")
        n = n + 1
        If Not existing.Exists(parts(0) & "|" & parts(1)) Then
            rs.AddNew
            rs!Category = parts(0)
            rs!Code = parts(1)
            rs!TitleFa = parts(2)
            rs!SortOrder = n
            rs!IsActive = True
            rs.Update
        End If
    Next item
    rs.Close

    SeedSetting be, "CompanyName", T("app.company"), False
    SeedSetting be, "SchemaVersion", CStr(SCHEMA_VERSION), True
    SeedSetting be, "InstalledAt", Format$(Now(), "yyyy-mm-dd hh:nn:ss"), False

    Set rs = be.OpenRecordset("SELECT Count(*) AS N FROM tblUsers", dbOpenSnapshot)
    n = rs!n
    rs.Close
    If n = 0 Then
        salt = NewSalt()
        Set rs = be.OpenRecordset("tblUsers", dbOpenDynaset)
        rs.AddNew
        rs!FullName = T("seed.admin_name")
        rs!UserName = "admin"
        rs!RoleCode = "ADMIN"
        rs!PwdSalt = salt
        rs!PwdHash = HashPassword("admin", salt)
        rs!MustChangePwd = True
        rs!IsActive = True
        rs.Update
        rs.Close
    End If
End Sub

Private Sub SeedSetting(ByVal be As DAO.Database, ByVal settingName As String, ByVal settingValue As String, ByVal overwrite As Boolean)
    Dim rs As DAO.Recordset
    Set rs = be.OpenRecordset("SELECT * FROM tblSettings WHERE SettingName=" & SqlStr(settingName), dbOpenDynaset)
    If rs.EOF Then
        rs.AddNew
        rs!SettingName = settingName
        rs!SettingValue = settingValue
        rs.Update
    ElseIf overwrite Then
        If Val(Nz(rs!SettingValue, "0")) < Val(settingValue) Then
            rs.Edit
            rs!SettingValue = settingValue
            rs.Update
        End If
    End If
    rs.Close
End Sub

' ---------------------------------------------------------------------
'  Linked tables
' ---------------------------------------------------------------------

Private Sub LinkBackend(ByVal bePath As String)
    Dim db As DAO.Database, be As DAO.Database, td As DAO.TableDef, ln As DAO.TableDef, names As Collection, nm As Variant
    Set names = New Collection
    Set be = DBEngine.OpenDatabase(bePath, False, True)
    For Each td In be.TableDefs
        If Left$(td.Name, 4) <> "MSys" And Left$(td.Name, 1) <> "~" Then names.Add td.Name
    Next td
    be.Close
    Set db = CurrentDb
    For Each nm In names
        If TableExistsIn(db, CStr(nm)) Then db.TableDefs.Delete CStr(nm)
        Set ln = db.CreateTableDef(CStr(nm))
        ln.Connect = ";DATABASE=" & bePath
        ln.SourceTableName = CStr(nm)
        db.TableDefs.Append ln
    Next nm
    db.TableDefs.Refresh
End Sub

' ---------------------------------------------------------------------
'  Queries (reports and history lists, with Persian column titles)
' ---------------------------------------------------------------------

Private Function Col(ByVal key As String) As String
    Dim s As String
    s = T(key)
    s = Replace(s, "[", "(")
    s = Replace(s, "]", ")")
    s = Replace(s, ".", "")
    s = Replace(s, "!", "")
    s = Replace(s, "`", "")
    Col = " AS [" & s & "]"
End Function

Private Sub MakeQuery(ByVal queryName As String, ByVal sql As String)
    Dim db As DAO.Database, qd As DAO.QueryDef
    Set db = CurrentDb
    For Each qd In db.QueryDefs
        If qd.Name = queryName Then
            db.QueryDefs.Delete queryName
            Exit For
        End If
    Next qd
    db.CreateQueryDef queryName, sql
End Sub

Private Sub BuildQueries()
    Dim s As String, fromC As String, selC As String

    fromC = " FROM ((tblComplaints AS c LEFT JOIN tblCustomers AS cu ON c.CustomerID=cu.CustomerID)" & _
            " LEFT JOIN tblVehicles AS v ON c.VehicleID=v.VehicleID) LEFT JOIN tblUsers AS u ON c.OwnerUserID=u.UserID"
    selC = "SELECT c.ComplaintID" & Col("col.id") & ", JDate(c.CreatedAt)" & Col("col.created") & ", cu.FullName" & Col("col.customer") & _
           ", cu.Mobile" & Col("col.mobile") & ", v.PlateNumber" & Col("col.plate") & ", c.SubjectText" & Col("col.subject") & _
           ", LK('ComplaintStatus',c.StatusCode)" & Col("col.status") & ", LK('Priority',c.PriorityCode)" & Col("col.priority") & _
           ", u.FullName" & Col("col.owner") & ", JDate(c.DueAt)" & Col("col.due") & ", DateDiff('d',c.CreatedAt,Date())" & Col("col.age")
    MakeQuery "qryRptOpenComplaints", selC & fromC & " WHERE c.StatusCode<>'CLOSED' ORDER BY c.DueAt, c.ComplaintID"
    MakeQuery "qryRptOverdueComplaints", selC & fromC & " WHERE c.StatusCode<>'CLOSED' AND c.DueAt<Date() ORDER BY c.DueAt"

    s = "SELECT a.ActionID" & Col("col.action_id") & ", a.ComplaintID" & Col("col.id") & ", cu.FullName" & Col("col.customer") & _
        ", c.SubjectText" & Col("col.subject") & _
        ", IIf(a.PlanStatus='PENDING'," & SqlStr(T("lbl.phase_plan")) & "," & SqlStr(T("lbl.phase_result")) & ")" & Col("col.phase") & _
        ", IIf(a.PlanStatus='PENDING',a.PlanText,a.ExecutionText)" & Col("col.text") & _
        ", JDate(IIf(a.PlanStatus='PENDING',a.PlannedAt,a.ExecutedAt))" & Col("col.sent_at") & _
        " FROM (tblCorrectiveActions AS a INNER JOIN tblComplaints AS c ON a.ComplaintID=c.ComplaintID)" & _
        " LEFT JOIN tblCustomers AS cu ON c.CustomerID=cu.CustomerID" & _
        " WHERE a.PlanStatus='PENDING' OR a.ResultStatus='PENDING' ORDER BY a.ActionID"
    MakeQuery "qryRptPendingApprovals", s

    s = "SELECT LK('ComplaintStatus',s.StatusCode)" & Col("col.status") & ", s.Cnt" & Col("col.count") & _
        " FROM (SELECT StatusCode, Count(*) AS Cnt FROM tblComplaints GROUP BY StatusCode) AS s ORDER BY s.Cnt DESC"
    MakeQuery "qryRptComplaintsByStatus", s

    s = "SELECT m.JMonth" & Col("col.month") & ", Count(*)" & Col("col.count") & ", Sum(IIf(m.StatusCode='CLOSED',1,0))" & Col("col.closed") & _
        " FROM (SELECT Left(JDate(CreatedAt),7) AS JMonth, StatusCode FROM tblComplaints) AS m GROUP BY m.JMonth ORDER BY m.JMonth DESC"
    MakeQuery "qryRptComplaintsByMonth", s

    s = "SELECT i.InteractionID" & Col("col.id") & ", JDate(i.FollowUpAt)" & Col("col.followup") & ", cu.FullName" & Col("col.customer") & _
        ", cu.Mobile" & Col("col.mobile") & ", i.SubjectText" & Col("col.subject") & ", LK('Channel',i.ChannelCode)" & Col("col.channel") & _
        ", u.FullName" & Col("col.user") & ", i.ResultText" & Col("col.result") & _
        " FROM (tblCRMInteractions AS i LEFT JOIN tblCustomers AS cu ON i.CustomerID=cu.CustomerID)" & _
        " LEFT JOIN tblUsers AS u ON i.UserID=u.UserID" & _
        " WHERE i.FollowUpDone=False AND i.FollowUpAt<Date()+1 ORDER BY i.FollowUpAt"
    MakeQuery "qryRptFollowUps", s

    s = "SELECT t.TaskID" & Col("col.id") & ", t.TitleText" & Col("col.title") & ", u.FullName" & Col("col.assignee") & _
        ", LK('Priority',t.PriorityCode)" & Col("col.priority") & ", JDate(t.DueAt)" & Col("col.due") & _
        ", LK('TaskStatus',t.StatusCode)" & Col("col.status") & ", DateDiff('d',t.DueAt,Date())" & Col("col.days_late") & _
        " FROM tblTasks AS t LEFT JOIN tblUsers AS u ON t.AssignedTo=u.UserID" & _
        " WHERE t.DueAt<Date() AND t.StatusCode NOT IN ('DONE','CANCELLED') ORDER BY t.DueAt"
    MakeQuery "qryRptOverdueTasks", s

    s = "SELECT l.LetterID" & Col("col.id") & ", l.LetterNo" & Col("col.letter_no") & ", LK('LetterDirection',l.DirectionCode)" & Col("col.direction") & _
        ", JDate(l.LetterAt)" & Col("col.date") & ", l.SubjectText" & Col("col.subject") & ", l.SenderText" & Col("col.sender") & _
        ", l.ReceiverText" & Col("col.receiver") & ", u.FullName" & Col("col.assignee") & ", LK('LetterStatus',l.StatusCode)" & Col("col.status") & _
        " FROM tblLetters AS l LEFT JOIN tblUsers AS u ON l.AssignedTo=u.UserID" & _
        " WHERE l.StatusCode NOT IN ('ANSWERED','ARCHIVED') ORDER BY l.LetterAt DESC"
    MakeQuery "qryRptOpenLetters", s

    s = "SELECT v.VehicleID" & Col("col.id") & ", cu.FullName" & Col("col.customer") & ", cu.Mobile" & Col("col.mobile") & _
        ", v.PlateNumber" & Col("col.plate") & ", v.ModelName" & Col("col.model") & ", v.Odometer" & Col("col.odometer") & _
        ", s.NextMileage" & Col("col.next_mileage") & ", JDate(s.ServiceAt)" & Col("col.last_service") & _
        " FROM (tblVehicles AS v INNER JOIN tblServices AS s ON v.VehicleID=s.VehicleID)" & _
        " LEFT JOIN tblCustomers AS cu ON v.CustomerID=cu.CustomerID" & _
        " WHERE s.ServiceID=(SELECT Max(s2.ServiceID) FROM tblServices AS s2 WHERE s2.VehicleID=v.VehicleID)" & _
        " AND ((s.NextMileage>0 AND v.Odometer>=s.NextMileage-500) OR s.ServiceAt<Date()-150) ORDER BY s.ServiceAt"
    MakeQuery "qryRptServiceDue", s

    s = "SELECT ServiceName" & Col("col.service") & ", Count(*)" & Col("col.count") & ", Sum(CostAmount)" & Col("col.total_cost") & _
        " FROM tblServices GROUP BY ServiceName ORDER BY Count(*) DESC"
    MakeQuery "qryRptServicesByType", s

    s = "SELECT c.CustomerID" & Col("col.id") & ", c.FullName" & Col("col.customer") & ", c.Mobile" & Col("col.mobile") & _
        ", c.CityText" & Col("col.city") & _
        ", (SELECT Count(*) FROM tblVehicles AS v WHERE v.CustomerID=c.CustomerID)" & Col("col.vehicles") & _
        ", (SELECT Count(*) FROM tblComplaints AS k WHERE k.CustomerID=c.CustomerID)" & Col("col.complaints") & _
        ", (SELECT Count(*) FROM tblComplaints AS k2 WHERE k2.CustomerID=c.CustomerID AND k2.StatusCode<>'CLOSED')" & Col("col.open_complaints") & _
        " FROM tblCustomers AS c ORDER BY c.FullName"
    MakeQuery "qryRptCustomers", s

    s = "SELECT h.ComplaintID, JDate(h.EventAt) & ' ' & Format(h.EventAt,'hh:nn')" & Col("col.date") & ", h.EventText" & Col("col.event") & _
        ", h.OldValue" & Col("col.old") & ", h.NewValue" & Col("col.new") & ", h.DetailsText" & Col("col.details") & ", u.FullName" & Col("col.user") & _
        " FROM tblComplaintHistory AS h LEFT JOIN tblUsers AS u ON h.ActorUserID=u.UserID ORDER BY h.HistoryID DESC"
    MakeQuery "qryComplaintHistoryList", s

    s = "SELECT h.LetterID, JDate(h.EventAt) & ' ' & Format(h.EventAt,'hh:nn')" & Col("col.date") & ", h.EventText" & Col("col.event") & _
        ", h.DetailsText" & Col("col.details") & ", u.FullName" & Col("col.user") & _
        " FROM tblLetterHistory AS h LEFT JOIN tblUsers AS u ON h.ActorUserID=u.UserID ORDER BY h.HistoryID DESC"
    MakeQuery "qryLetterHistoryList", s
End Sub

' ---------------------------------------------------------------------
'  Form building helpers
' ---------------------------------------------------------------------

Private Function Q(ByVal s As String) As String
    Q = Chr$(34) & Replace(s, Chr$(34), Chr$(34) & Chr$(34)) & Chr$(34)
End Function

' Event/ControlSource expression: Ex("OpenAppForm", "frmCustomers") -> =OpenAppForm("frmCustomers")
Private Function Ex(ByVal fn As String, ParamArray args() As Variant) As String
    Dim s As String, i As Long
    For i = LBound(args) To UBound(args)
        If i > LBound(args) Then s = s & ","
        s = s & Q(CStr(args(i)))
    Next i
    Ex = "=" & fn & "(" & s & ")"
End Function

Private Sub SetP(ByVal obj As Object, ByVal propName As String, ByVal v As Variant)
    On Error Resume Next
    obj.Properties(propName).Value = v
End Sub

Private Sub StyleText(ByVal c As Control, ByVal fontSize As Long, ByVal bold As Boolean, ByVal align As Long)
    SetP c, "FontName", UI_FONT
    SetP c, "FontSize", fontSize
    SetP c, "FontBold", bold
    SetP c, "TextAlign", align
    SetP c, "ReadingOrder", 2
End Sub

Private Function Lbl(ByVal sec As Long, ByVal caption As String, ByVal x As Long, ByVal y As Long, ByVal w As Long, ByVal h As Long, _
                     Optional ByVal fontSize As Long = 10, Optional ByVal bold As Boolean = False, Optional ByVal fore As Long = -1, _
                     Optional ByVal align As Long = 3, Optional ByVal parentCtl As String = "") As Control
    Dim c As Control
    Set c = CreateControl(mFN, acLabel, sec, parentCtl, "", x, y, w, h)
    c.Caption = caption
    StyleText c, fontSize, bold, align
    If fore <> -1 Then c.ForeColor = fore
    Set Lbl = c
End Function

Private Function Txt(ByVal sec As Long, ByVal ctlName As String, ByVal boundTo As String, ByVal x As Long, ByVal y As Long, ByVal w As Long, ByVal h As Long) As Control
    Dim c As Control
    Set c = CreateControl(mFN, acTextBox, sec, "", boundTo, x, y, w, h)
    c.Name = ctlName
    StyleText c, 10, False, 3
    Set Txt = c
End Function

Private Function Btn(ByVal sec As Long, ByVal ctlName As String, ByVal caption As String, ByVal onClick As String, _
                     ByVal x As Long, ByVal y As Long, ByVal w As Long, ByVal h As Long, Optional ByVal roleTag As String = "") As Control
    Dim c As Control
    Set c = CreateControl(mFN, acCommandButton, sec, "", "", x, y, w, h)
    c.Name = ctlName
    c.Caption = caption
    c.OnClick = onClick
    StyleText c, 10, True, 2
    If Len(roleTag) > 0 Then c.Tag = roleTag
    Set Btn = c
End Function

Private Function Rect(ByVal sec As Long, ByVal x As Long, ByVal y As Long, ByVal w As Long, ByVal h As Long, ByVal color As Long) As Control
    Dim c As Control
    Set c = CreateControl(mFN, acRectangle, sec, "", "", x, y, w, h)
    c.BackStyle = 1
    c.BackColor = color
    c.BorderStyle = 0
    Set Rect = c
End Function

Private Function NewForm() As Form
    Dim f As Form
    Set f = CreateForm
    mFN = f.Name
    SetP f, "RecordSelectors", False
    SetP f, "DividingLines", False
    SetP f, "AutoCenter", True
    Set NewForm = f
End Function

Private Sub DialogProps(ByVal f As Form)
    SetP f, "NavigationButtons", False
    SetP f, "ScrollBars", 0
    SetP f, "PopUp", True
    SetP f, "Modal", True
    SetP f, "BorderStyle", 3
    SetP f, "MinMaxButtons", 0
    SetP f, "Moveable", True
End Sub

Private Sub SaveFormAs(ByVal finalName As String)
    DoCmd.Close acForm, mFN, acSaveYes
    DoCmd.Rename finalName, acForm, mFN
End Sub

Private Function EnableHeader(ByVal f As Form) As Boolean
    Dim h As Long
    On Error Resume Next
    h = f.Section(acHeader).Height
    If Err.Number = 0 Then
        EnableHeader = True
        Exit Function
    End If
    Err.Clear
    DoCmd.RunCommand acCmdFormHdrFtr
    If Err.Number <> 0 Then Exit Function
    h = f.Section(acHeader).Height
    If Err.Number <> 0 Then Exit Function
    EnableHeader = True
    f.Section(acFooter).Height = 0
    f.Section(acFooter).Visible = False
End Function

Private Sub DeleteAllForms()
    Dim names As Collection, ao As AccessObject, nm As Variant
    Set names = New Collection
    For Each ao In CurrentProject.AllForms
        names.Add ao.Name
    Next ao
    For Each nm In names
        DoCmd.DeleteObject acForm, CStr(nm)
    Next nm
End Sub

' ---------------------------------------------------------------------
'  Forms
' ---------------------------------------------------------------------

Private Sub BuildAllForms()
    DeleteAllForms
    BuildLoginForm
    BuildChangePasswordForm
    BuildPromptForm
    BuildMainForm
    BuildReportsForm
    BuildDataForms
    BuildListForm "frmComplaintHistory", "ttl.complaint_history", "qryComplaintHistoryList"
    BuildListForm "frmLetterHistory", "ttl.letter_history", "qryLetterHistoryList"
    mFN = ""
End Sub

Private Sub BuildLoginForm()
    Dim f As Form, c As Control
    Set f = NewForm()
    f.Caption = T("app.title")
    f.Width = 7000
    f.Section(acDetail).Height = 4300
    f.Section(acDetail).BackColor = CLR_BODY
    DialogProps f
    SetP f, "CloseButton", False
    f.OnLoad = "=AppStartup()"
    Rect acDetail, 0, 0, 7000, 1300, CLR_HEAD
    Lbl acDetail, T("app.company"), 200, 200, 6600, 520, 16, True, CLR_WHITE, 2
    Lbl acDetail, T("app.subtitle"), 200, 780, 6600, 380, 9, False, CLR_WHITE, 2
    Set c = Txt(acDetail, "txtUser", "", 500, 1700, 4100, 380)
    SetP c, "ReadingOrder", 1
    SetP c, "TextAlign", 1
    Lbl acDetail, T("lbl.username"), 4750, 1700, 1800, 380, 10, True, CLR_TITLE, 3, "txtUser"
    Set c = Txt(acDetail, "txtPwd", "", 500, 2250, 4100, 380)
    c.InputMask = "Password"
    SetP c, "ReadingOrder", 1
    SetP c, "TextAlign", 1
    Lbl acDetail, T("lbl.password"), 4750, 2250, 1800, 380, 10, True, CLR_TITLE, 3, "txtPwd"
    Set c = Btn(acDetail, "cmdLogin", T("btn.login"), "=DoLogin()", 3600, 2950, 2000, 480)
    c.Default = True
    Set c = Btn(acDetail, "cmdExit", T("btn.exit"), "=AppExit()", 1400, 2950, 2000, 480)
    c.Cancel = True
    Lbl acDetail, T("lbl.version") & " " & APP_VERSION, 200, 3750, 6600, 300, 8, False, CLR_MUTED, 2
    SaveFormAs "frmLogin"
End Sub

Private Sub BuildChangePasswordForm()
    Dim f As Form, c As Control, y As Long, i As Long, names As Variant, keys As Variant
    Set f = NewForm()
    f.Caption = T("ttl.change_password")
    f.Width = 7000
    f.Section(acDetail).Height = 4200
    f.Section(acDetail).BackColor = CLR_BODY
    DialogProps f
    SetP f, "CloseButton", False
    f.OnLoad = "=ChangePwdLoad()"
    Lbl acDetail, T("ttl.change_password"), 200, 150, 6600, 450, 13, True, CLR_TITLE, 2
    Set c = Lbl(acDetail, T("msg.must_change_pwd"), 200, 650, 6600, 420, 9, False, CLR_ACCENT, 2)
    c.Name = "lblForce"
    names = Array("txtOld", "txtNew", "txtNew2")
    keys = Array("lbl.old_password", "lbl.new_password", "lbl.new_password2")
    y = 1250
    For i = 0 To 2
        Set c = Txt(acDetail, CStr(names(i)), "", 400, y, 3900, 380)
        c.InputMask = "Password"
        SetP c, "ReadingOrder", 1
        Lbl acDetail, T(CStr(keys(i))), 4400, y, 2300, 380, 10, True, CLR_TITLE, 3, CStr(names(i))
        y = y + 520
    Next i
    Set c = Btn(acDetail, "cmdSave", T("btn.save"), "=DoChangePassword()", 3600, 3050, 2000, 480)
    c.Default = True
    Set c = Btn(acDetail, "cmdCancel", T("btn.cancel"), "=ChangePwdCancel()", 1400, 3050, 2000, 480)
    c.Cancel = True
    SaveFormAs "frmChangePassword"
End Sub

Private Sub BuildPromptForm()
    Dim f As Form, c As Control
    Set f = NewForm()
    f.Caption = T("app.title")
    f.Width = 7600
    f.Section(acDetail).Height = 2900
    f.Section(acDetail).BackColor = CLR_BODY
    DialogProps f
    SetP f, "CloseButton", False
    f.OnLoad = "=PromptLoad()"
    Set c = Lbl(acDetail, "-", 200, 150, 7200, 900, 10, True, CLR_TITLE, 3)
    c.Name = "lblPrompt"
    Set c = Txt(acDetail, "txtValue", "", 200, 1150, 7200, 700)
    SetP c, "EnterKeyBehavior", False
    SetP c, "ScrollBars", 2
    Set c = Btn(acDetail, "cmdOK", T("btn.ok"), "=PromptOK()", 4300, 2100, 1800, 460)
    c.Default = True
    Set c = Btn(acDetail, "cmdCancel", T("btn.cancel"), "=PromptCancel()", 2300, 2100, 1800, 460)
    c.Cancel = True
    SaveFormAs "frmPrompt"
End Sub

Private Sub BuildMainForm()
    Dim f As Form, c As Control, i As Long, cl As Long, row As Long, x As Long, y As Long
    Dim tiles As Variant, menu As Variant, m As Variant
    Const TILE_W As Long = 3600, TILE_H As Long = 1050, GAP As Long = 300
    Const BTN_W As Long = 3600, BTN_H As Long = 500

    Set f = NewForm()
    f.Caption = T("app.title")
    f.Width = FORM_W
    SetP f, "NavigationButtons", False
    SetP f, "ScrollBars", 2
    f.OnLoad = "=MainOnLoad()"
    f.OnActivate = "=MainRefresh()"
    f.OnClose = "=MainClosed()"
    f.OnTimer = "=MainRefresh()"
    f.TimerInterval = 120000
    f.Section(acDetail).Height = 9000
    f.Section(acDetail).BackColor = CLR_BODY

    Rect acDetail, 0, 0, FORM_W, 1450, CLR_HEAD
    Lbl acDetail, T("app.company"), 300, 150, FORM_W - 600, 650, 22, True, CLR_WHITE, 2
    Lbl acDetail, T("app.subtitle"), 300, 850, FORM_W - 600, 420, 11, False, CLR_WHITE, 2
    Set c = Lbl(acDetail, "-", FORM_W - 300 - 6000, 1550, 6000, 380, 10, True, CLR_TITLE, 3)
    c.Name = "lblUser"
    Set c = Lbl(acDetail, "-", 300, 1550, 5000, 380, 10, False, CLR_MUTED, 1)
    c.Name = "lblToday"

    ' Dashboard tiles (click to open the filtered list)
    tiles = Array("OPEN", "OVERDUE", "PENDING", "FOLLOWUP", "MYTASKS", "LETTERS")
    For i = 0 To UBound(tiles)
        cl = i Mod 3
        row = i \ 3
        x = FORM_W - 300 - (cl + 1) * TILE_W - cl * GAP
        y = 2100 + row * (TILE_H + 200)
        Rect acDetail, x, y, TILE_W, TILE_H, CLR_TILE
        Set c = Lbl(acDetail, T("tile." & tiles(i)), x + 100, y + 80, TILE_W - 200, 340, 10, True, CLR_MUTED, 2)
        c.Name = "lblTile" & i
        c.OnClick = Ex("DashOpen", tiles(i))
        Set c = Txt(acDetail, "txtTile" & i, "", x + 100, y + 430, TILE_W - 200, 540)
        c.ControlSource = Ex("DashCount", tiles(i))
        c.OnClick = Ex("DashOpen", tiles(i))
        c.Locked = True
        c.TabStop = False
        c.BorderStyle = 0
        c.BackStyle = 0
        c.Format = "#,##0"
        StyleText c, 20, True, 2
        If tiles(i) = "OVERDUE" Then c.ForeColor = CLR_ACCENT Else c.ForeColor = CLR_TITLE
    Next i

    ' Menu buttons: key, action, role tag
    menu = Array( _
        Array("customers", Ex("OpenAppForm", "frmCustomers"), ""), _
        Array("vehicles", Ex("OpenAppForm", "frmVehicles"), ""), _
        Array("complaints", Ex("OpenAppForm", "frmComplaints"), ""), _
        Array("actions", Ex("OpenAppForm", "frmCorrectiveActions"), ""), _
        Array("approvals", Ex("DashOpen", "PENDING"), "MANAGER"), _
        Array("crm", Ex("OpenAppForm", "frmCRM"), ""), _
        Array("letters", Ex("OpenAppForm", "frmLetters"), ""), _
        Array("tasks", Ex("OpenAppForm", "frmTasks"), ""), _
        Array("services", Ex("OpenAppForm", "frmServices"), ""), _
        Array("reports", Ex("OpenAppForm", "frmReports"), ""), _
        Array("users", Ex("OpenAppForm", "frmUsers"), "ADMIN"), _
        Array("lookups", Ex("OpenAppForm", "frmLookups"), "ADMIN"), _
        Array("backup", "=AdminBackup()", "ADMIN"), _
        Array("relink", "=AdminRelink()", "ADMIN"), _
        Array("chpwd", Ex("OpenAppForm", "frmChangePassword"), ""), _
        Array("logout", "=AppLogout()", ""), _
        Array("exit", "=AppExit()", ""))
    For i = 0 To UBound(menu)
        m = menu(i)
        cl = i Mod 3
        row = i \ 3
        x = FORM_W - 300 - (cl + 1) * BTN_W - cl * GAP
        y = 4700 + row * (BTN_H + 110)
        Btn acDetail, "cmd_" & m(0), T("menu." & m(0)), CStr(m(1)), x, y, BTN_W, BTN_H, CStr(m(2))
    Next i
    Lbl acDetail, T("lbl.version") & " " & APP_VERSION, 300, 8500, FORM_W - 600, 300, 8, False, CLR_MUTED, 2
    SaveFormAs "frmMain"
End Sub

Private Sub BuildReportsForm()
    Dim f As Form, reps As Variant, i As Long, y As Long
    Set f = NewForm()
    f.Caption = T("ttl.reports")
    f.Width = 10000
    SetP f, "NavigationButtons", False
    reps = Split(REPORT_LIST, ";")
    f.Section(acDetail).Height = 1200 + (UBound(reps) + 1) * 560 + 600
    f.Section(acDetail).BackColor = CLR_BODY
    Rect acDetail, 0, 0, 10000, 850, CLR_HEAD
    Lbl acDetail, T("ttl.reports"), 300, 180, 9400, 500, 15, True, CLR_WHITE, 2
    y = 1100
    For i = 0 To UBound(reps)
        Lbl acDetail, T("rpt." & reps(i)), 3900, y, 5800, 420, 10, True, CLR_TITLE, 3
        Btn acDetail, "cmdView" & i, T("btn.view"), Ex("ReportOpen", reps(i)), 2100, y, 1650, 420
        Btn acDetail, "cmdXls" & i, T("btn.excel"), Ex("ReportExport", reps(i)), 300, y, 1650, 420
        y = y + 560
    Next i
    Btn acDetail, "cmdClose", T("btn.close"), Ex("CloseForm", "frmReports"), 300, y + 100, 1650, 420
    SaveFormAs "frmReports"
End Sub

' Datasheet list of a query (read-only), column titles from the query aliases.
Private Sub BuildListForm(ByVal formName As String, ByVal titleKey As String, ByVal queryName As String)
    Dim f As Form, qd As DAO.QueryDef, fl As DAO.Field, c As Control, lb As Control, y As Long, i As Long, cap As String
    Set f = NewForm()
    f.Caption = T(titleKey)
    f.RecordSource = queryName
    f.DefaultView = 2
    f.AllowEdits = False
    f.AllowAdditions = False
    f.AllowDeletions = False
    SetP f, "Orientation", 1
    Set qd = CurrentDb.QueryDefs(queryName)
    y = 100
    For Each fl In qd.Fields
        Set c = CreateControl(mFN, acTextBox, acDetail, "", fl.Name, 3000, y, 5000, 340)
        c.Name = "c" & i
        StyleText c, 10, False, 3
        cap = fl.Name
        If cap Like "*ID" Then cap = T("f." & cap)
        Set lb = CreateControl(mFN, acLabel, acDetail, c.Name, "", 300, y, 2600, 340)
        lb.Caption = cap
        y = y + 420
        i = i + 1
    Next fl
    SaveFormAs formName
End Sub

' ---------------------------------------------------------------------
'  Data entry forms (split form: record on top, searchable list below)
'  Field spec: Array(FieldName, LabelKey, Kind [, Options])
'     Kind: T text, M memo, N number, C money, D date (+Jalali), B check,
'           L:Cat lookup code, LT:Cat lookup text, CUST, VEH, USR, CMP
'     Options (";"-separated): lock, def=<expr>, chk=mobile|ncode|digits,
'           au=<AfterUpdate expression>
'  Extra buttons: Array(Name, CaptionKey, OnClick [, RoleTag])
' ---------------------------------------------------------------------

Private Sub BuildDataForms()
    Dim s As Variant, e As Variant

    s = Array( _
        Array("CustomerID", "f.CustomerID", "N", "lock"), _
        Array("FullName", "f.FullName", "T"), _
        Array("Mobile", "f.Mobile", "T", "chk=mobile"), _
        Array("Phone", "f.Phone", "T", "chk=digits"), _
        Array("NationalCode", "f.NationalCode", "T", "chk=ncode"), _
        Array("CityText", "f.CityText", "T"), _
        Array("AddressText", "f.AddressText", "M"), _
        Array("Notes", "f.Notes", "M"), _
        Array("CreatedAt", "f.CreatedAt", "D", "lock"), _
        Array("CreatedBy", "f.CreatedBy", "USR", "lock;def==CurrentUserID()"))
    e = Array( _
        Array("cmd_Vehicles", "btn.vehicles", Ex("OpenChild", "frmCustomers", "frmVehicles", "CustomerID", "")), _
        Array("cmd_Complaints", "btn.complaints", Ex("OpenChild", "frmCustomers", "frmComplaints", "CustomerID", "")), _
        Array("cmd_CRM", "btn.crm", Ex("OpenChild", "frmCustomers", "frmCRM", "CustomerID", "")))
    BuildDataForm "frmCustomers", "ttl.customers", "SELECT * FROM tblCustomers ORDER BY CustomerID DESC", _
        "#CustomerID;FullName;Mobile;Phone;NationalCode", s, e

    s = Array( _
        Array("VehicleID", "f.VehicleID", "N", "lock"), _
        Array("CustomerID", "f.CustomerID", "CUST"), _
        Array("PlateNumber", "f.PlateNumber", "T"), _
        Array("VIN", "f.VIN", "T", "chk=upper"), _
        Array("ModelName", "f.ModelName", "LT:VehicleModel"), _
        Array("ColorText", "f.ColorText", "T"), _
        Array("ProductionYear", "f.ProductionYear", "T", "chk=digits"), _
        Array("Odometer", "f.Odometer", "N"), _
        Array("SaleDate", "f.SaleDate", "D"), _
        Array("WarrantyEnd", "f.WarrantyEnd", "D"), _
        Array("Notes", "f.Notes", "M"), _
        Array("CreatedBy", "f.CreatedBy", "USR", "lock;def==CurrentUserID()"))
    e = Array( _
        Array("cmd_Services", "btn.services", Ex("OpenChild", "frmVehicles", "frmServices", "VehicleID", "")), _
        Array("cmd_Complaints", "btn.complaints", Ex("OpenChild", "frmVehicles", "frmComplaints", "VehicleID", "CustomerID")))
    BuildDataForm "frmVehicles", "ttl.vehicles", "SELECT * FROM tblVehicles ORDER BY VehicleID DESC", _
        "#VehicleID;PlateNumber;VIN;ModelName;@CUST", s, e

    s = Array( _
        Array("ComplaintID", "f.ComplaintID", "N", "lock"), _
        Array("CustomerID", "f.CustomerID", "CUST", "au=" & Ex("DataFormCurrent", "frmComplaints")), _
        Array("VehicleID", "f.VehicleID", "VEH", "au=" & Ex("VehiclePicked", "frmComplaints")), _
        Array("ChannelCode", "f.ChannelCode", "L:Channel"), _
        Array("SubjectText", "f.SubjectText", "T"), _
        Array("ComplaintText", "f.ComplaintText", "M"), _
        Array("RootCause", "f.RootCause", "M"), _
        Array("PriorityCode", "f.PriorityCode", "L:Priority"), _
        Array("OwnerUserID", "f.OwnerUserID", "USR"), _
        Array("DueAt", "f.DueAt", "D", "def=Date()+7"), _
        Array("StatusCode", "f.StatusCode", "L:ComplaintStatus", "lock"), _
        Array("SatisfactionCode", "f.SatisfactionCode", "L:Satisfaction"), _
        Array("CreatedAt", "f.CreatedAt", "D", "lock"), _
        Array("ClosedAt", "f.ClosedAt", "D", "lock"), _
        Array("CreatedBy", "f.CreatedBy", "USR", "lock;def==CurrentUserID()"))
    e = Array( _
        Array("cmd_Actions", "btn.actions", Ex("OpenChild", "frmComplaints", "frmCorrectiveActions", "ComplaintID", "")), _
        Array("cmd_History", "btn.history", "=OpenComplaintHistory()"), _
        Array("cmd_Task", "btn.new_task", Ex("OpenChild", "frmComplaints", "frmTasks", "ComplaintID", "CustomerID")), _
        Array("cmd_CloseComplaint", "btn.close_complaint", "=WfCloseComplaint()", "MANAGER"))
    BuildDataForm "frmComplaints", "ttl.complaints", "SELECT * FROM tblComplaints ORDER BY ComplaintID DESC", _
        "#ComplaintID;SubjectText;ComplaintText;@CUST;@VEH", s, e

    s = Array( _
        Array("ActionID", "f.ActionID", "N", "lock"), _
        Array("ComplaintID", "f.ComplaintID", "CMP"), _
        Array("PlanText", "f.PlanText", "M"), _
        Array("PlanStatus", "f.PlanStatus", "L:PlanStatus", "lock"), _
        Array("PlannedAt", "f.PlannedAt", "D", "lock"), _
        Array("PlanApprovedBy", "f.PlanApprovedBy", "USR", "lock"), _
        Array("ExecutionText", "f.ExecutionText", "M"), _
        Array("ResultStatus", "f.ResultStatus", "L:ResultStatus", "lock"), _
        Array("ExecutedAt", "f.ExecutedAt", "D", "lock"), _
        Array("ResultApprovedBy", "f.ResultApprovedBy", "USR", "lock"), _
        Array("CreatedBy", "f.CreatedBy", "USR", "lock;def==CurrentUserID()"))
    e = Array( _
        Array("cmd_SubmitPlan", "btn.submit_plan", "=WfSubmitPlan()", "WORKER"), _
        Array("cmd_ApprovePlan", "btn.approve_plan", "=WfApprovePlan()", "MANAGER"), _
        Array("cmd_RejectPlan", "btn.reject_plan", "=WfRejectPlan()", "MANAGER"), _
        Array("cmd_SubmitResult", "btn.submit_result", "=WfSubmitResult()", "WORKER"), _
        Array("cmd_ApproveResult", "btn.approve_result", "=WfApproveResult()", "MANAGER"), _
        Array("cmd_RejectResult", "btn.reject_result", "=WfRejectResult()", "MANAGER"))
    BuildDataForm "frmCorrectiveActions", "ttl.actions", "SELECT * FROM tblCorrectiveActions ORDER BY ActionID DESC", _
        "#ActionID;#ComplaintID;PlanText;ExecutionText", s, e

    s = Array( _
        Array("InteractionID", "f.InteractionID", "N", "lock"), _
        Array("CustomerID", "f.CustomerID", "CUST", "au=" & Ex("DataFormCurrent", "frmCRM")), _
        Array("VehicleID", "f.VehicleID", "VEH", "au=" & Ex("VehiclePicked", "frmCRM")), _
        Array("ChannelCode", "f.ChannelCode", "L:Channel"), _
        Array("SubjectText", "f.SubjectText", "T"), _
        Array("DetailText", "f.DetailText", "M"), _
        Array("ContactAt", "f.ContactAt", "D"), _
        Array("FollowUpAt", "f.FollowUpAt", "D"), _
        Array("FollowUpDone", "f.FollowUpDone", "B"), _
        Array("ResultText", "f.ResultText", "T"), _
        Array("UserID", "f.UserID", "USR", "lock;def==CurrentUserID()"))
    e = Array(Array("cmd_FollowUpDone", "btn.followup_done", "=CrmFollowUpDone()"))
    BuildDataForm "frmCRM", "ttl.crm", "SELECT * FROM tblCRMInteractions ORDER BY InteractionID DESC", _
        "#InteractionID;SubjectText;DetailText;ResultText;@CUST", s, e

    s = Array( _
        Array("TaskID", "f.TaskID", "N", "lock"), _
        Array("TitleText", "f.TitleText", "T"), _
        Array("DescriptionText", "f.DescriptionText", "M"), _
        Array("AssignedTo", "f.AssignedTo", "USR"), _
        Array("PriorityCode", "f.PriorityCode", "L:Priority"), _
        Array("DueAt", "f.DueAt", "D"), _
        Array("StatusCode", "f.StatusCode", "L:TaskStatus"), _
        Array("ComplaintID", "f.ComplaintID", "CMP", "au=" & Ex("ComplaintPicked", "frmTasks")), _
        Array("CustomerID", "f.CustomerID", "CUST"), _
        Array("CompletedAt", "f.CompletedAt", "D", "lock"), _
        Array("CreatedBy", "f.CreatedBy", "USR", "lock;def==CurrentUserID()"))
    e = Array(Array("cmd_TaskDone", "btn.task_done", "=TaskDone()"))
    BuildDataForm "frmTasks", "ttl.tasks", "SELECT * FROM tblTasks ORDER BY TaskID DESC", _
        "#TaskID;TitleText;DescriptionText", s, e

    s = Array( _
        Array("LetterID", "f.LetterID", "N", "lock"), _
        Array("LetterNo", "f.LetterNo", "T", "chk=text"), _
        Array("DirectionCode", "f.DirectionCode", "L:LetterDirection"), _
        Array("LetterAt", "f.LetterAt", "D"), _
        Array("SubjectText", "f.SubjectText", "T"), _
        Array("SenderText", "f.SenderText", "T"), _
        Array("ReceiverText", "f.ReceiverText", "T"), _
        Array("BodyText", "f.BodyText", "M"), _
        Array("AssignedTo", "f.AssignedTo", "USR"), _
        Array("StatusCode", "f.StatusCode", "L:LetterStatus", "au==LetterStatusChanged()"), _
        Array("AttachmentPath", "f.AttachmentPath", "T", "lock"), _
        Array("CreatedBy", "f.CreatedBy", "USR", "lock;def==CurrentUserID()"))
    e = Array( _
        Array("cmd_Attach", "btn.attach", "=LetterAttach()"), _
        Array("cmd_OpenAttach", "btn.open_attachment", "=LetterOpenAttachment()"), _
        Array("cmd_LetterHistory", "btn.history", "=OpenLetterHistory()"))
    BuildDataForm "frmLetters", "ttl.letters", "SELECT * FROM tblLetters ORDER BY LetterID DESC", _
        "#LetterID;LetterNo;SubjectText;SenderText;ReceiverText;BodyText", s, e

    s = Array( _
        Array("ServiceID", "f.ServiceID", "N", "lock"), _
        Array("VehicleID", "f.VehicleID", "VEH"), _
        Array("ServiceName", "f.ServiceName", "LT:ServiceType"), _
        Array("ServiceAt", "f.ServiceAt", "D"), _
        Array("Mileage", "f.Mileage", "N"), _
        Array("NextMileage", "f.NextMileage", "N"), _
        Array("CostAmount", "f.CostAmount", "C"), _
        Array("Notes", "f.Notes", "M"), _
        Array("CreatedBy", "f.CreatedBy", "USR", "lock;def==CurrentUserID()"))
    BuildDataForm "frmServices", "ttl.services", "SELECT * FROM tblServices ORDER BY ServiceID DESC", _
        "#ServiceID;ServiceName;Notes;@VEH", s, Array(), "=ServiceSaved()"

    s = Array( _
        Array("UserID", "f.UserID", "N", "lock"), _
        Array("FullName", "f.FullName", "T"), _
        Array("UserName", "f.UserName", "T"), _
        Array("RoleCode", "f.RoleCode", "L:Role"), _
        Array("IsActive", "f.IsActive", "B"), _
        Array("MustChangePwd", "f.MustChangePwd", "B"), _
        Array("LastLoginAt", "f.LastLoginAt", "D", "lock"))
    e = Array(Array("cmd_SetPwd", "btn.set_password", "=UserSetPassword()", "ADMIN"))
    BuildDataForm "frmUsers", "ttl.users", "SELECT UserID, FullName, UserName, RoleCode, IsActive, MustChangePwd, LastLoginAt FROM tblUsers ORDER BY FullName", _
        "FullName;UserName", s, e

    s = Array( _
        Array("LookupID", "f.LookupID", "N", "lock"), _
        Array("Category", "f.Category", "T"), _
        Array("Code", "f.Code", "T"), _
        Array("TitleFa", "f.TitleFa", "T"), _
        Array("SortOrder", "f.SortOrder", "N"), _
        Array("IsActive", "f.IsActive", "B"))
    BuildDataForm "frmLookups", "ttl.lookups", "SELECT * FROM tblLookups ORDER BY Category, SortOrder", _
        "Category;Code;TitleFa", s, Array(), "", "=ResetCaches()"
End Sub

Private Sub BuildDataForm(ByVal formName As String, ByVal titleKey As String, ByVal source As String, ByVal searchTag As String, _
                          ByVal specs As Variant, ByVal extras As Variant, Optional ByVal formAfterUpdate As String = "", _
                          Optional ByVal formOnClose As String = "")
    Dim f As Form, hasHdr As Boolean, hdrSec As Long, hdrH As Long, y As Long, i As Long, nExtra As Long
    Set f = NewForm()
    f.RecordSource = source
    f.Caption = T(titleKey)
    f.Width = FORM_W
    f.Tag = searchTag
    f.AllowDeletions = False
    f.OnLoad = Ex("DataFormLoad", formName)
    f.OnCurrent = Ex("DataFormCurrent", formName)
    If Len(formAfterUpdate) > 0 Then f.AfterUpdate = formAfterUpdate
    If Len(formOnClose) > 0 Then f.OnClose = formOnClose
    SetP f, "NavigationButtons", True
    SetP f, "Cycle", 1
    SetP f, "DefaultView", 5             ' split form
    SetP f, "SplitFormOrientation", 1    ' datasheet below the record
    SetP f, "SplitFormDatasheet", 1      ' datasheet is read-only

    nExtra = UBound(extras) - LBound(extras) + 1
    hdrH = 1250
    If nExtra > 0 Then hdrH = 1730
    hasHdr = EnableHeader(f)
    If hasHdr Then
        hdrSec = acHeader
        f.Section(acHeader).Height = hdrH
        f.Section(acHeader).BackColor = CLR_HEAD
        y = 250
    Else
        hdrSec = acDetail
        y = hdrH + 200
    End If
    f.Section(acDetail).BackColor = CLR_BODY
    BuildHeader formName, titleKey, hdrSec, hasHdr, extras

    For i = LBound(specs) To UBound(specs)
        AddField formName, specs(i), y
    Next i
    f.Section(acDetail).Height = y + 200
    SaveFormAs formName
End Sub

Private Sub BuildHeader(ByVal formName As String, ByVal titleKey As String, ByVal sec As Long, ByVal onDark As Boolean, ByVal extras As Variant)
    Dim fore As Long, x As Long, i As Long, c As Control, std As Variant, e As Variant, roleTag As String
    If onDark Then fore = CLR_WHITE Else fore = CLR_TITLE
    Lbl sec, T("app.company") & "  |  " & T(titleKey), 300, 120, FORM_W - 600, 480, 14, True, fore, 3
    Lbl sec, T("lbl.search"), FORM_W - 300 - 1300, 720, 1300, 360, 10, True, fore, 3
    x = FORM_W - 300 - 1300 - 80 - 3700
    Set c = Txt(sec, "txtFind", "", x, 720, 3700, 360)
    c.AfterUpdate = Ex("FormCmd", formName, "find")
    std = Array("find", "all", "new", "save", "delete", "close")
    For i = 0 To UBound(std)
        x = x - 80 - 950
        roleTag = ""
        If std(i) = "delete" Then roleTag = "MANAGER"
        Btn sec, "cmd_" & std(i), T("btn." & std(i)), Ex("FormCmd", formName, std(i)), x, 710, 950, 380, roleTag
    Next i
    x = FORM_W - 300
    For i = LBound(extras) To UBound(extras)
        e = extras(i)
        x = x - 1880
        roleTag = ""
        If UBound(e) >= 3 Then roleTag = e(3)
        Btn sec, CStr(e(0)), T(CStr(e(1))), CStr(e(2)), x, 1200, 1800, 400, roleTag
    Next i
End Sub

Private Sub AddField(ByVal formName As String, ByVal spec As Variant, ByRef y As Long)
    Dim fld As String, lblKey As String, kind As String, opts As String, h As Long, cat As String
    Dim c As Control, lb As Control, j As Control, o As Variant
    fld = spec(0)
    lblKey = spec(1)
    kind = spec(2)
    If UBound(spec) >= 3 Then opts = spec(3)
    h = 360
    If kind = "M" Then h = 900
    If InStr(kind, ":") > 0 Then cat = Mid$(kind, InStr(kind, ":") + 1)

    If kind = "D" Then
        Set c = CreateControl(mFN, acTextBox, acDetail, "", fld, DATE_X, y, DATE_W, h)
        c.Format = "Short Date"
        SetP c, "ShowDatePicker", 1
    ElseIf kind = "B" Then
        Set c = CreateControl(mFN, acCheckBox, acDetail, "", fld, IN_X + IN_W - 300, y + 50, 300, 260)
    ElseIf Left$(kind, 2) = "L:" Then
        Set c = Combo(fld, "SELECT Code, TitleFa FROM tblLookups WHERE Category='" & cat & "' ORDER BY SortOrder, TitleFa", 2, y, h)
    ElseIf Left$(kind, 3) = "LT:" Then
        Set c = Combo(fld, "SELECT TitleFa FROM tblLookups WHERE Category='" & cat & "' AND IsActive=True ORDER BY SortOrder, TitleFa", 1, y, h)
    ElseIf kind = "CUST" Then
        Set c = Combo(fld, SQL_CUST, 2, y, h)
    ElseIf kind = "VEH" Then
        Set c = Combo(fld, SQL_VEH_BASE & " ORDER BY v.PlateNumber", 2, y, h)
    ElseIf kind = "USR" Then
        Set c = Combo(fld, SQL_USR, 2, y, h)
    ElseIf kind = "CMP" Then
        Set c = Combo(fld, SQL_CMP, 2, y, h)
    Else
        Set c = CreateControl(mFN, acTextBox, acDetail, "", fld, IN_X, y, IN_W, h)
        If kind = "M" Then
            SetP c, "ScrollBars", 2
            SetP c, "EnterKeyBehavior", True
        ElseIf kind = "C" Then
            c.Format = "#,##0"
        End If
    End If
    c.Name = "c_" & fld
    StyleText c, 10, False, 3

    Set lb = CreateControl(mFN, acLabel, acDetail, c.Name, "", LBL_X, y, LBL_W, 360)
    lb.Name = "l_" & fld
    lb.Caption = T(lblKey)
    StyleText lb, 10, True, 3
    lb.ForeColor = CLR_TITLE

    If kind = "D" Then
        Set j = CreateControl(mFN, acTextBox, acDetail, "", "", IN_X, y, J_W, h)
        j.ControlSource = "=JDate([" & fld & "])"
        j.Locked = True
        j.TabStop = False
        j.BackColor = CLR_LOCK
        StyleText j, 10, True, 2
        j.ForeColor = CLR_TITLE
        ' The control name becomes the datasheet column title.
        On Error Resume Next
        j.Name = T(lblKey) & " - " & T("lbl.shamsi")
        If Err.Number <> 0 Then j.Name = "j_" & fld
        On Error GoTo 0
    End If

    For Each o In Split(opts, ";")
        If o = "lock" Then
            c.Locked = True
            c.TabStop = False
            SetP c, "BackColor", CLR_LOCK
        ElseIf Left$(o, 4) = "def=" Then
            c.DefaultValue = Mid$(o, 5)
        ElseIf Left$(o, 4) = "chk=" Then
            c.AfterUpdate = Ex("NormField", formName, c.Name, Mid$(o, 5))
        ElseIf Left$(o, 3) = "au=" Then
            c.AfterUpdate = Mid$(o, 4)
        End If
    Next o
    y = y + h + 110
End Sub

Private Function Combo(ByVal fld As String, ByVal sql As String, ByVal cols As Long, ByVal y As Long, ByVal h As Long) As Control
    Dim c As Control
    Set c = CreateControl(mFN, acComboBox, acDetail, "", fld, IN_X, y, IN_W, h)
    c.RowSourceType = "Table/Query"
    c.RowSource = sql
    c.ColumnCount = cols
    c.BoundColumn = 1
    If cols = 2 Then
        c.ColumnWidths = "0;" & CStr(IN_W)
        c.LimitToList = True
    Else
        c.LimitToList = False
    End If
    c.ListWidth = IN_W
    c.ListRows = 16
    Set Combo = c
End Function

' ---------------------------------------------------------------------
'  Start-up options of the front-end
' ---------------------------------------------------------------------

Private Sub SetStartupProps()
    Dim db As DAO.Database
    Set db = CurrentDb
    SetDbProp db, "AppTitle", dbText, T("app.title")
    SetDbProp db, "StartupForm", dbText, "frmLogin"
    SetDbProp db, "StartupShowDBWindow", dbBoolean, False
    SetDbProp db, "StartupShowStatusBar", dbBoolean, True
    SetDbProp db, "AllowShortcutMenus", dbBoolean, True
    SetDbProp db, "AllowBuiltinToolbars", dbBoolean, True
    On Error Resume Next
    Application.SetOption "Auto Compact", True
    Application.SetOption "Track Name AutoCorrect Info", False
    Application.SetOption "Perform Name AutoCorrect", False
    Application.RefreshTitleBar
End Sub

Private Sub SetDbProp(ByVal db As DAO.Database, ByVal propName As String, ByVal propType As Long, ByVal v As Variant)
    On Error Resume Next
    db.Properties(propName) = v
    If Err.Number <> 0 Then
        Err.Clear
        db.Properties.Append db.CreateProperty(propName, propType, v)
    End If
End Sub
