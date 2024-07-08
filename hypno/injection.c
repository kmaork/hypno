#include <Python.h>
#include <errno.h>
#include <linux/limits.h>

#define MAX_PYTHON_CODE_SIZE 60500
#define STR_EXPAND(tok) #tok
#define STR(tok) STR_EXPAND(tok)

PyMODINIT_FUNC PyInit_injection(void) {return NULL;}

volatile char PYTHON_CODE[MAX_PYTHON_CODE_SIZE + 1] = "\0--- hypno code start ---" STR(MAX_PYTHON_CODE_SIZE);
volatile char PYTHON_SCRIPT_PATH[PATH_MAX] = "\0--- hypno script path start ---" STR(PATH_MAX);

void run_python_code() {
    if (PYTHON_CODE[0]) {
        int saved_errno = errno;
        PyGILState_STATE gstate = PyGILState_Ensure();
        if (PYTHON_CODE[0] != '\0') {
            PyRun_SimpleString(PYTHON_CODE);
        } else if (PYTHON_SCRIPT_PATH[0] != '\0') {
            int fp = fopen(PYTHON_SCRIPT_PATH, "r");
            PyRun_SimpleFile(fp, PYTHON_SCRIPT_PATH);
            fclose(fp);
        }

        PyGILState_Release(gstate);
        errno = saved_errno;
    }
}

#ifdef _WIN32
    #include <windows.h>

    BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpReserved) {
        switch( fdwReason ) {
            case DLL_PROCESS_ATTACH:
                run_python_code();
                break;
        }
        return TRUE;
    }
#else
    __attribute__((constructor))
    static void init(void) {
        run_python_code();
    }
#endif
