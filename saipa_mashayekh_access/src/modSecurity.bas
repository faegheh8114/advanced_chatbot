Attribute VB_Name = "modSecurity"
Option Compare Database
Option Explicit

' Password hashing with the Windows CNG API (bcrypt.dll): salted SHA-256,
' stretched over several thousand rounds. Works in 32-bit and 64-bit Office
' (Access 2010 or newer). Passwords are never stored in plain text.

Private Declare PtrSafe Function BCryptOpenAlgorithmProvider Lib "bcrypt.dll" (ByRef phAlgorithm As LongPtr, ByVal pszAlgId As LongPtr, ByVal pszImplementation As LongPtr, ByVal dwFlags As Long) As Long
Private Declare PtrSafe Function BCryptCloseAlgorithmProvider Lib "bcrypt.dll" (ByVal hAlgorithm As LongPtr, ByVal dwFlags As Long) As Long
Private Declare PtrSafe Function BCryptCreateHash Lib "bcrypt.dll" (ByVal hAlgorithm As LongPtr, ByRef phHash As LongPtr, ByVal pbHashObject As LongPtr, ByVal cbHashObject As Long, ByVal pbSecret As LongPtr, ByVal cbSecret As Long, ByVal dwFlags As Long) As Long
Private Declare PtrSafe Function BCryptHashData Lib "bcrypt.dll" (ByVal hHash As LongPtr, ByVal pbInput As LongPtr, ByVal cbInput As Long, ByVal dwFlags As Long) As Long
Private Declare PtrSafe Function BCryptFinishHash Lib "bcrypt.dll" (ByVal hHash As LongPtr, ByVal pbOutput As LongPtr, ByVal cbOutput As Long, ByVal dwFlags As Long) As Long
Private Declare PtrSafe Function BCryptDestroyHash Lib "bcrypt.dll" (ByVal hHash As LongPtr) As Long
Private Declare PtrSafe Function BCryptGenRandom Lib "bcrypt.dll" (ByVal hAlgorithm As LongPtr, ByVal pbBuffer As LongPtr, ByVal cbBuffer As Long, ByVal dwFlags As Long) As Long

Private Const BCRYPT_USE_SYSTEM_PREFERRED_RNG As Long = 2
Private Const HASH_ROUNDS As Long = 3000
Public Const MIN_PASSWORD_LEN As Long = 4

Public Function NewSalt() As String
    Dim b(15) As Byte, i As Long, s As String
    If BCryptGenRandom(0, VarPtr(b(0)), 16, BCRYPT_USE_SYSTEM_PREFERRED_RNG) <> 0 Then
        Randomize
        For i = 0 To 15
            b(i) = Int(Rnd() * 256)
        Next i
    End If
    For i = 0 To 15
        s = s & Right$("0" & Hex$(b(i)), 2)
    Next i
    NewSalt = LCase$(s)
End Function

Public Function HashPassword(ByVal pwd As String, ByVal salt As String) As String
    Dim hAlg As LongPtr, algId As String, h As String, i As Long
    Dim errNo As Long, errDesc As String
    algId = "SHA256"
    If BCryptOpenAlgorithmProvider(hAlg, StrPtr(algId), 0, 0) <> 0 Then
        Err.Raise vbObjectError + 901, "HashPassword", "SHA-256 provider is not available on this computer."
    End If
    On Error GoTo Fail
    h = salt & ":" & pwd
    For i = 1 To HASH_ROUNDS
        h = Sha256Hex(hAlg, h & ":" & salt)
    Next i
    BCryptCloseAlgorithmProvider hAlg, 0
    HashPassword = h
    Exit Function
Fail:
    errNo = Err.Number: errDesc = Err.Description
    BCryptCloseAlgorithmProvider hAlg, 0
    Err.Raise errNo, "HashPassword", errDesc
End Function

Public Function VerifyPassword(ByVal pwd As String, ByVal salt As String, ByVal storedHash As String) As Boolean
    If Len(storedHash) = 0 Or Len(salt) = 0 Then Exit Function
    VerifyPassword = (StrComp(HashPassword(pwd, salt), storedHash, vbBinaryCompare) = 0)
End Function

Private Function Sha256Hex(ByVal hAlg As LongPtr, ByVal textIn As String) As String
    Dim hHash As LongPtr, inBytes() As Byte, outBytes(31) As Byte, i As Long, s As String
    inBytes = textIn
    If BCryptCreateHash(hAlg, hHash, 0, 0, 0, 0, 0) <> 0 Then Err.Raise vbObjectError + 902, , "BCryptCreateHash failed"
    If BCryptHashData(hHash, VarPtr(inBytes(0)), UBound(inBytes) + 1, 0) <> 0 Then
        BCryptDestroyHash hHash
        Err.Raise vbObjectError + 903, , "BCryptHashData failed"
    End If
    If BCryptFinishHash(hHash, VarPtr(outBytes(0)), 32, 0) <> 0 Then
        BCryptDestroyHash hHash
        Err.Raise vbObjectError + 904, , "BCryptFinishHash failed"
    End If
    BCryptDestroyHash hHash
    For i = 0 To 31
        s = s & Right$("0" & Hex$(outBytes(i)), 2)
    Next i
    Sha256Hex = LCase$(s)
End Function
