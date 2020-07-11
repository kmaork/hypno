#include <Python.h>
#include <errno.h>

static void init(void) __attribute__((constructor));

void inject_py() {
    PyGILState_STATE gstate;
    gstate = PyGILState_Ensure();
    PyRun_SimpleString("print('LOLZ')");
    PyGILState_Release(gstate);
}

static void init(void) {
    int saved_errno = errno;
    inject_py();
    errno = saved_errno;
}