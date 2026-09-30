#include <Python.h>
#include <errno.h>

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
    /*
     * On Windows the loader runs DllMain in a fresh thread with a normal stack,
     * so it is safe to enter the interpreter synchronously here. We still touch
     * SAFE (honored on POSIX) so its marker isn't stripped from the DLL and
     * hypno can locate it when patching.
     */
    (void)SAFE[0];
    {
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
