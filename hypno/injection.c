#define _GNU_SOURCE

#include <Python.h>
#include <errno.h>

#define MAX_PYTHON_CODE_SIZE 60500
#define STR_EXPAND(tok) #tok
#define STR(tok) STR_EXPAND(tok)

char PYTHON_CODE[MAX_PYTHON_CODE_SIZE + 1] = "\0--- hypno code start ---" STR(MAX_PYTHON_CODE_SIZE);

__attribute__((constructor))
static void init(void) {
    if (PYTHON_CODE[0]) {
        int saved_errno = errno;
        PyGILState_STATE gstate = PyGILState_Ensure();
        PyRun_SimpleString(PYTHON_CODE);
        PyGILState_Release(gstate);
        errno = saved_errno;
    }
}
