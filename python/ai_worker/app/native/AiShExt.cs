// AiShExt.cs — shell extension ai_organizer (C#, .NET Framework, tanpa NuGet).
// Klik kanan folder/background -> submenu dinamis:
//   Scan di sini | Analisis AI di sini | Dokumen AI | --- | rekomendasi AI (top-3)
// Install/uninstall via integrations/explorer.py (HKCU, tanpa admin).
// Compile: csc /target:library /out:AiShExt.dll AiShExt.cs
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using System.Text;
using Microsoft.Win32;

namespace AiOrganizerShell
{
    #region COM interfaces (raw, tanpa SharpShell)
    [ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown),
     Guid("000214E8-0000-0000-C000-000000000046")]
    internal interface IShellExtInit
    {
        void Initialize(IntPtr pidlFolder, IDataObject pDataObj, IntPtr hKeyProgID);
    }

    [ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown),
     Guid("000214E4-0000-0000-C000-000000000046")]
    internal interface IContextMenu
    {
        [PreserveSig]
        int QueryContextMenu(IntPtr hMenu, uint indexMenu, uint idCmdFirst,
                             uint idCmdLast, uint uFlags);
        void InvokeCommand(IntPtr pici);
        void GetCommandString(UIntPtr idCmd, uint uType, IntPtr pReserved,
                              StringBuilder pszName, uint cchMax);
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct CMINVOKECOMMANDINFO
    {
        public uint cbSize; public uint fMask; public IntPtr hwnd;
        public IntPtr lpVerb; public IntPtr lpParameters; public IntPtr lpDirectory;
        public int nShow; public uint dwHotKey; public IntPtr hIcon;
    }

    internal static class Native
    {
        [DllImport("shell32.dll")] public static extern bool SHGetPathFromIDList(
            IntPtr pidl, StringBuilder path);
        [DllImport("user32.dll")] public static extern IntPtr CreatePopupMenu();
        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        public static extern bool InsertMenu(IntPtr hMenu, uint uPosition, uint uFlags,
            UIntPtr uIDNewItem, string lpNewItem);
        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        public static extern bool AppendMenu(IntPtr hMenu, uint uFlags,
            UIntPtr uIDNewItem, string lpNewItem);
        public const uint MF_STRING = 0x0000, MF_POPUP = 0x0010, MF_SEPARATOR = 0x0800;
        public const uint CMF_DEFAULTONLY = 0x0001;
    }
    #endregion

    [ComVisible(true), Guid("7E3A9B2C-4D1F-4A8E-9C6B-5F0A2D4E8C1A"),
     ClassInterface(ClassInterfaceType.None), ProgId("AiOrganizer.ShellExt")]
    public class ShellExt : IShellExtInit, IContextMenu
    {
        public const string CLSID = "{7E3A9B2C-4D1F-4A8E-9C6B-5F0A2D4E8C1A}";
        private string folder = "";
        private readonly List<Rec> recs = new List<Rec>();
        private string appExe = "";

        private class Rec { public string Text = ""; public string Path = ""; public string Args = ""; }

        public void Initialize(IntPtr pidlFolder, IDataObject pDataObj, IntPtr hKeyProgID)
        {
            folder = FolderFromData(pDataObj) ?? PathFromPidl(pidlFolder) ?? "";
            LoadConfig();
        }

        private static string PathFromPidl(IntPtr pidl)
        {
            if (pidl == IntPtr.Zero) return null;
            var sb = new StringBuilder(260 * 2);
            return Native.SHGetPathFromIDList(pidl, sb) ? sb.ToString() : null;
        }

        private static string FolderFromData(IDataObject data)
        {
            if (data == null) return null;
            try
            {
                var fmt = new FORMATETC
                {
                    cfFormat = (short)CLIPFORMAT.CF_HDROP,
                    ptd = IntPtr.Zero, dwAspect = DVASPECT.DVASPECT_CONTENT,
                    lindex = -1, tymed = TYMED.TYMED_HGLOBAL
                };
                STGMEDIUM med;
                data.GetData(ref fmt, out med);
                try
                {
                    uint n = DragQueryFile(med.unionmember, 0xFFFFFFFF, null, 0);
                    if (n == 0) return null;
                    var sb = new StringBuilder(260 * 2);
                    DragQueryFile(med.unionmember, 0, sb, sb.Capacity);
                    string p = sb.ToString();
                    if (string.IsNullOrEmpty(p)) return null;
                    return Directory.Exists(p) ? p : Path.GetDirectoryName(p);
                }
                finally { ReleaseStgMedium(ref med); }
            }
            catch { return null; }
        }

        [DllImport("shell32.dll")] private static extern uint DragQueryFile(
            IntPtr hDrop, uint iFile, StringBuilder lpszFile, int cch);
        [DllImport("ole32.dll")] private static extern void ReleaseStgMedium(ref STGMEDIUM pmedium);
        private enum CLIPFORMAT : short { CF_HDROP = 15 }

        private void LoadConfig()
        {
            try
            {
                using (var k = Registry.CurrentUser.OpenSubKey(
                    @"Software\Classes\CLSID\" + CLSID))
                {
                    appExe = (k == null ? "" : (k.GetValue("AppExe") as string)) ?? "";
                    string root = (k == null ? "" : (k.GetValue("AppRoot") as string)) ?? "";
                    if (!string.IsNullOrEmpty(root))
                    {
                        string jf = Path.Combine(root, "results", "reports", "recommend.json");
                        if (File.Exists(jf)) ParseRecs(File.ReadAllText(jf));
                    }
                }
            }
            catch { }
        }

        // Parser JSON mini: [{"text":"..","path":"..","args":"..."}]
        private void ParseRecs(string json)
        {
            try
            {
                int i = 0;
                while (recs.Count < 3 && (i = json.IndexOf('{', i)) >= 0)
                {
                    int j = json.IndexOf('}', i);
                    if (j < 0) break;
                    string obj = json.Substring(i, j - i + 1);
                    var r = new Rec
                    {
                        Text = JsonStr(obj, "text"),
                        Path = JsonStr(obj, "path"),
                        Args = JsonStr(obj, "args")
                    };
                    if (!string.IsNullOrEmpty(r.Text)) recs.Add(r);
                    i = j + 1;
                }
            }
            catch { }
        }

        private static string JsonStr(string obj, string key)
        {
            string k = "\"" + key + "\"";
            int i = obj.IndexOf(k, StringComparison.Ordinal);
            if (i < 0) return "";
            i = obj.IndexOf(':', i);
            if (i < 0) return "";
            i++;
            while (i < obj.Length && char.IsWhiteSpace(obj[i])) i++;
            if (i < obj.Length && obj[i] == '"')
            {
                i++;
                var sb = new StringBuilder();
                while (i < obj.Length && obj[i] != '"')
                {
                    if (obj[i] == '\\' && i + 1 < obj.Length) { i++; sb.Append(obj[i]); }
                    else sb.Append(obj[i]);
                    i++;
                }
                return sb.ToString().Replace("\\\\", "\\");
            }
            return "";
        }

        public int QueryContextMenu(IntPtr hMenu, uint indexMenu, uint idCmdFirst,
                                    uint idCmdLast, uint uFlags)
        {
            if ((uFlags & Native.CMF_DEFAULTONLY) != 0) return 0;
            if (string.IsNullOrEmpty(folder) || !Directory.Exists(folder)) return 0;
            if (string.IsNullOrEmpty(appExe) || !File.Exists(appExe)) return 0;

            IntPtr sub = Native.CreatePopupMenu();
            uint id = 0;
            Native.AppendMenu(sub, Native.MF_STRING, (UIntPtr)(idCmdFirst + id++), "Scan di sini");
            Native.AppendMenu(sub, Native.MF_STRING, (UIntPtr)(idCmdFirst + id++), "Analisis AI di sini");
            Native.AppendMenu(sub, Native.MF_STRING, (UIntPtr)(idCmdFirst + id++), "Buka ai_organizer GUI");
            if (recs.Count > 0)
            {
                Native.AppendMenu(sub, Native.MF_SEPARATOR, UIntPtr.Zero, null);
                foreach (var r in recs)
                    Native.AppendMenu(sub, Native.MF_STRING, (UIntPtr)(idCmdFirst + id++),
                                      ("Rekomendasi: " + r.Text).Replace("&", "&&"));
            }
            Native.InsertMenu(hMenu, indexMenu, Native.MF_STRING | Native.MF_POPUP,
                              (UIntPtr)(ulong)sub.ToInt64(), "ai_organizer");
            return (int)id; // jumlah id yang dipakai (HRESULT S_OK implisit via PreserveSig? kembalikan count)
        }

        public void InvokeCommand(IntPtr pici)
        {
            var info = (CMINVOKECOMMANDINFO)Marshal.PtrToStructure(pici, typeof(CMINVOKECOMMANDINFO));
            if ((info.fMask & 0x2000 /*CMIC_MASK_UNICODE*/) != 0) return;
            int idx = info.lpVerb.ToInt32(); // MAKEINTRESOURCE -> index
            string args = null;
            if (idx == 0) args = "cli scan \"" + folder + "\"";
            else if (idx == 1) args = "cli analyze \"" + folder + "\"";
            else if (idx == 2) args = "gui";
            else
            {
                int ri = idx - 3;
                if (ri >= 0 && ri < recs.Count)
                {
                    var r = recs[ri];
                    args = string.IsNullOrEmpty(r.Args)
                        ? "cli scan \"" + (string.IsNullOrEmpty(r.Path) ? folder : r.Path) + "\""
                        : r.Args;
                }
            }
            if (args == null) return;
            try
            {
                Process.Start(new ProcessStartInfo
                {
                    FileName = appExe, Arguments = args, UseShellExecute = false,
                    CreateNoWindow = true,
                    WorkingDirectory = Path.GetDirectoryName(appExe) ?? ""
                });
            }
            catch { }
        }

        public void GetCommandString(UIntPtr idCmd, uint uType, IntPtr pReserved,
                                     StringBuilder pszName, uint cchMax)
        {
        }
    }
}
