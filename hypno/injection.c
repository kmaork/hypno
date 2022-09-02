#include <Python.h>
#include <errno.h>

#define MAX_PYTHON_CODE_SIZE 60500
#define STR_EXPAND(tok) #tok
#define STR(tok) STR_EXPAND(tok)

PyMODINIT_FUNC PyInit_injection(void) {return NULL;}

char PYTHON_CODE[MAX_PYTHON_CODE_SIZE + 1] = "\0--- hypno code start ---" STR(MAX_PYTHON_CODE_SIZE);

int run_python_code(char *code) {
    PyRun_SimpleString(code);
    return 0;
}

void inject_python() {
    if (PYTHON_CODE[0]) {
        int saved_errno = errno;
        Py_AddPendingCall(&run_python_code, &PYTHON_CODE);
        errno = saved_errno;
    }
}

#ifdef _WIN32
    #include <windows.h>

    BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpReserved) {
        switch( fdwReason ) {
            case DLL_PROCESS_ATTACH:
                inject_python();
                return FALSE;
                break;
        }
        return TRUE;
    }
#else
    __attribute__((constructor))
    static void init(void) {
        inject_python();
    }
#endif
