#include <Python.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>

#define MAX_PYTHON_CODE_SIZE 60500
#define STR_EXPAND(tok) #tok
#define STR(tok) STR_EXPAND(tok)

PyMODINIT_FUNC PyInit_injection(void) {return NULL;}

/*
 * These two buffers are patched in-place by hypno (see api.py) before the
 * shared library is injected. The printable markers let hypno locate the
 * buffers inside the compiled library; the byte immediately before each marker
 * holds the actual value (the code to run / the "safe" flag).
 */
volatile char PYTHON_CODE[MAX_PYTHON_CODE_SIZE + 1] = "\0--- hypno code start ---" STR(MAX_PYTHON_CODE_SIZE);
volatile char SAFE[] = "\1--- hypno safe marker ---";

static int run_python_code(void *unused) {
    PyRun_SimpleString((const char *)PYTHON_CODE);
    return 0;
}

static void inject_python(void) {
    int saved_errno;
    if (!PYTHON_CODE[0]) {
        return;
    }
    saved_errno = errno;
#ifdef _WIN32
    if (SAFE[0]) {
        /*
         * Safe path (the default). Running the code here, inside DllMain, would hold the loader lock while
         * waiting for the GIL, which deadlocks if the GIL holder loads a DLL. So we only schedule the code to
         * run on the main thread at its next safe point. We are unloaded as soon as DllMain returns, so the
         * scheduled function is Python's own PyRun_SimpleString, with a heap copy of the code (leaked, as
         * nothing outlives us to free it).
         */
        size_t size = strlen((const char *)PYTHON_CODE) + 1;
        char *code = malloc(size);
        if (code != NULL) {
            memcpy(code, (const char *)PYTHON_CODE, size);
            Py_AddPendingCall((int (*)(void *))PyRun_SimpleString, code);
        }
    } else {
        PyGILState_STATE gstate = PyGILState_Ensure();
        run_python_code(NULL);
        PyGILState_Release(gstate);
    }
#else
    if (SAFE[0]) {
        /*
         * Safe path (the default). On Linux/macOS the injector runs this
         * constructor by hijacking a target thread and pointing it at a small
         * scratch stack. Entering the interpreter directly from there is unsafe
         * because the target thread may hold a non-reentrant lock, and on
         * CPython >= 3.14 it aborts outright: the C-stack overflow guard
         * rejects the foreign stack. So instead we only *schedule* the code and
         * let the interpreter run it at its next eval-breaker safe point, on a
         * real Python stack.
         */
        Py_AddPendingCall(&run_python_code, NULL);
    } else {
        /*
         * Immediate/unsafe path: run right here in the hijacked thread. This
         * can run code in the context of a specific thread (see run_in_thread),
         * but risks deadlocks and aborts on CPython >= 3.14.
         */
        PyGILState_STATE gstate = PyGILState_Ensure();
        run_python_code(NULL);
        PyGILState_Release(gstate);
    }
#endif
    errno = saved_errno;
}

#ifdef _WIN32
    #include <windows.h>

    BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpReserved) {
        if (fdwReason == DLL_PROCESS_ATTACH) {
            inject_python();
            /* Return FALSE so the loader unloads us immediately, releasing the
               temporary DLL file so hypno can delete it. */
            return FALSE;
        }
        return TRUE;
    }
#else
    __attribute__((constructor))
    static void init(void) {
        inject_python();
    }
#endif
