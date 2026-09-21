// AiHelper.cs — helper native kecil (C# .NET Framework, tanpa NuGet).
//   AiHelper.exe toast "judul" "pesan"   -> balon notifikasi Windows
//   AiHelper.exe activefolder            -> cetak folder Explorer aktif ("" bila tak ada)
// Compile: csc /target:exe /out:AiHelper.exe /reference:System.Windows.Forms.dll AiHelper.cs
using System;
using System.Reflection;
using System.Threading;
using System.Windows.Forms;

namespace AiOrganizerHelper
{
    internal static class Program
    {
        [STAThread]
        private static int Main(string[] args)
        {
            if (args.Length == 0) { Console.WriteLine("pakai: toast|activefolder"); return 2; }
            try
            {
                if (args[0] == "toast" && args.Length >= 3)
                {
                    using (var ni = new NotifyIcon())
                    {
                        ni.Icon = System.Drawing.SystemIcons.Information;
                        ni.Visible = true;
                        ni.BalloonTipTitle = args[1];
                        ni.BalloonTipText = args[2];
                        ni.ShowBalloonTip(8000);
                        Thread.Sleep(8500);
                    }
                    return 0;
                }
                if (args[0] == "activefolder")
                {
                    Console.WriteLine(ActiveExplorerFolder() ?? "");
                    return 0;
                }
            }
            catch (Exception e) { Console.Error.WriteLine(e.Message); return 1; }
            return 2;
        }

        // Late-bound Shell.Application (tanpa referensi SHDocVw/interop).
        private static string ActiveExplorerFolder()
        {
            try
            {
                Type t = Type.GetTypeFromProgID("Shell.Application");
                if (t == null) return "";
                object shell = Activator.CreateInstance(t);
                object wins = t.InvokeMember("Windows", BindingFlags.GetProperty, null, shell, null);
                var winsType = wins.GetType();
                int n = (int)winsType.InvokeMember("Count", BindingFlags.GetProperty, null, wins, null);
                for (int i = 0; i < n; i++)
                {
                    object w;
                    try { w = winsType.InvokeMember("Item", BindingFlags.InvokeMethod, null, wins, new object[] { i }); }
                    catch { continue; }
                    if (w == null) continue;
                    try
                    {
                        string loc = w.GetType().InvokeMember("LocationURL", BindingFlags.GetProperty,
                                                              null, w, null) as string;
                        if (!string.IsNullOrEmpty(loc) && loc.StartsWith("file:///", StringComparison.OrdinalIgnoreCase))
                        {
                            string p = Uri.UnescapeDataString(loc.Substring(8)).Replace('/', '\\');
                            if (System.IO.Directory.Exists(p)) return p;
                        }
                    }
                    catch { }
                }
            }
            catch { }
            return "";
        }
    }
}
