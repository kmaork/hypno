#define _GNU_SOURCE

#include <dlfcn.h>
#include <Python.h>
#include <errno.h>
#include <string.h>

static void init(void) __attribute__((constructor));

const char *get_lib_name() {
    Dl_info dl_info;
    dladdr((void *) get_lib_name, &dl_info);
    return dl_info.dli_fname;
}

void inject_py(const char *py_code) {
    PyGILState_STATE gstate;
    gstate = PyGILState_Ensure();
    PyRun_SimpleString(py_code);
    PyGILState_Release(gstate);
}

char *get_py_code_from_lib_name() {
    const char *lib_name = get_lib_name();
    int lib_name_len = strlen(lib_name);
    char *hex = strrchr(lib_name, '-') + 1;
    int py_code_len = (lib_name + lib_name_len - hex) / 2;
    char *py_code = malloc(py_code_len + 1);
    for (int py_code_i = 0; py_code_i < py_code_len; ++py_code_i) {
        hex += sscanf(hex, "%2hhx", &py_code[py_code_i]) * 2;
    }
    py_code[py_code_len] = '\0';
    return py_code;
}

static void init(void) {
    int saved_errno = errno;
    char *py_code = get_py_code_from_lib_name();
    inject_py(py_code);
    free(py_code);
    errno = saved_errno;
}