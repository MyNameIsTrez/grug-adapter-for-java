import json
import sys


def get_output(mod_api):
    output = ""

    output += '#include "headers/game_Game.h"\n'
    output += "\n"
    output += '#include "grug/grug.h"\n'
    output += "\n"
    output += "#include <assert.h>\n"
    output += "#include <stdbool.h>\n"
    output += "#include <stdio.h>\n"

    output += "\n"

    output += "typedef char* string;\n"
    output += "typedef int32_t i32;\n"
    output += "typedef uint64_t id;\n"

    output += "\n"

    for name, entity in mod_api["entities"].items():
        if "on_functions" not in entity:
            continue

        output += f"struct {name}_on_fns {{\n"

        for on_fn_name, on_fn in entity["on_functions"].items():
            output += f"    void (*{on_fn_name})(void *globals"

            # TODO: Allow passing arguments
            assert "arguments" not in on_fn

            output += ");\n"

        output += "};\n"

        output += "\n"

    output += "JNIEnv *global_env;\n"
    output += "jobject global_obj;\n"

    output += "\n"

    output += "jmethodID runtime_error_handler_id;\n"

    output += "\n"

    for name, entity in mod_api["entities"].items():
        output += f"jobject {name}_definition_obj;\n"

        for field in entity["fields"]:
            output += f"jfieldID {name}_definition_{field["name"]}_fid;\n"

        output += "\n"

    for name in mod_api["game_functions"].keys():
        output += f"jmethodID game_fn_{name}_id;\n"

    output += "\n"

    for name, entity in mod_api["entities"].items():
        output += f"void game_fn_define_{name}("

        for field_index, field in enumerate(entity["fields"]):
            if field_index > 0:
                output += ", "

            output += f"{field["type"]} c_{field["name"]}"

        output += ") {\n"

        output += "}\n"

        output += "\n"

    for i, (fn_name, fn) in enumerate(mod_api["game_functions"].items()):
        if i > 0:
            output += "\n"

        output += fn["return_type"] if "return_type" in fn else "void"

        output += f" game_fn_{fn_name}("

        for argument_index, argument in enumerate(fn["arguments"]):
            if argument_index > 0:
                output += ", "

            output += f"{argument["type"]} {argument["name"]}"

        output += ") {\n"

        output += "    "

        if "return_type" in fn:
            output += "return "

        output += "(*global_env)->Call"

        if "return_type" not in fn:
            output += "Void"
        elif fn["return_type"] == "id":
            output += "Int"
        else:
            # TODO: Support more types
            assert False

        output += f"Method(global_env, global_obj, game_fn_{fn_name}_id"

        for argument_index, argument in enumerate(fn["arguments"]):
            output += f", {argument["name"]}"

        output += ");\n"

        output += "}\n"

    output += """
void runtime_error_handler(char *reason, enum grug_runtime_error_type type, char *on_fn_name, char *on_fn_path) {
    jstring java_reason = (*global_env)->NewStringUTF(global_env, reason);
    jint java_type = type;
    jstring java_on_fn_name = (*global_env)->NewStringUTF(global_env, on_fn_name);
    jstring java_on_fn_path = (*global_env)->NewStringUTF(global_env, on_fn_path);

    (*global_env)->CallVoidMethod(global_env, global_obj, runtime_error_handler_id, java_reason, java_type, java_on_fn_name, java_on_fn_path);
}

JNIEXPORT void JNICALL Java_game_Game_grugSetRuntimeErrorHandler(JNIEnv *env, jobject obj) {
    (void)env;
    (void)obj;

    grug_set_runtime_error_handler(runtime_error_handler);
}

JNIEXPORT jboolean JNICALL Java_game_Game_errorHasChanged(JNIEnv *env, jobject obj) {
    (void)env;
    (void)obj;

    return grug_error.has_changed;
}

JNIEXPORT jboolean JNICALL Java_game_Game_loadingErrorInGrugFile(JNIEnv *env, jobject obj) {
    (void)env;
    (void)obj;

    return grug_loading_error_in_grug_file;
}

JNIEXPORT jstring JNICALL Java_game_Game_errorMsg(JNIEnv *env, jobject obj) {
    (void)env;
    (void)obj;

    return (*global_env)->NewStringUTF(global_env, grug_error.msg);
}

JNIEXPORT jstring JNICALL Java_game_Game_errorPath(JNIEnv *env, jobject obj) {
    (void)env;
    (void)obj;

    return (*global_env)->NewStringUTF(global_env, grug_error.path);
}

JNIEXPORT jstring JNICALL Java_game_Game_onFnName(JNIEnv *env, jobject obj) {
    (void)env;
    (void)obj;

    return (*global_env)->NewStringUTF(global_env, grug_on_fn_name);
}

JNIEXPORT jstring JNICALL Java_game_Game_onFnPath(JNIEnv *env, jobject obj) {
    (void)env;
    (void)obj;

    return (*global_env)->NewStringUTF(global_env, grug_on_fn_path);
}

JNIEXPORT jint JNICALL Java_game_Game_errorGrugCLineNumber(JNIEnv *env, jobject obj) {
    (void)env;
    (void)obj;

    return grug_error.grug_c_line_number;
}

JNIEXPORT jboolean JNICALL Java_game_Game_grugRegenerateModifiedMods(JNIEnv *env, jobject obj) {
    (void)env;
    (void)obj;

    return grug_regenerate_modified_mods();
}

JNIEXPORT jint JNICALL Java_game_Game_getGrugReloadsSize(JNIEnv *env, jobject obj) {
    (void)env;
    (void)obj;

    return grug_reloads_size;
}

JNIEXPORT void JNICALL Java_game_Game_fillReloadData(JNIEnv *env, jobject obj, jobject reload_data_object, jint reload_index) {
    (void)obj;

    struct grug_modified c_reload_data = grug_reloads[reload_index];

    jclass reload_data_class = (*env)->GetObjectClass(env, reload_data_object);

    jfieldID path_fid = (*env)->GetFieldID(env, reload_data_class, "path", "Ljava/lang/String;");
    jstring path = (*env)->NewStringUTF(env, c_reload_data.path);
    (*env)->SetObjectField(env, reload_data_object, path_fid, path);

    jfieldID old_dll_fid = (*env)->GetFieldID(env, reload_data_class, "oldDll", "J");
    (*env)->SetLongField(env, reload_data_object, old_dll_fid, (jlong)c_reload_data.old_dll);

    jfieldID file_fid = (*env)->GetFieldID(env, reload_data_class, "file", "Lgame/GrugFile;");
    jobject file_object = (*env)->GetObjectField(env, reload_data_object, file_fid);

    jclass file_class = (*env)->GetObjectClass(env, file_object);

    struct grug_file c_file = c_reload_data.file;

    jfieldID name_fid = (*env)->GetFieldID(env, file_class, "name", "Ljava/lang/String;");
    jstring name = (*env)->NewStringUTF(env, c_file.name);
    (*env)->SetObjectField(env, file_object, name_fid, name);

    jfieldID dll_fid = (*env)->GetFieldID(env, file_class, "dll", "J");
    (*env)->SetLongField(env, file_object, dll_fid, (jlong)c_file.dll);

    jfieldID define_fn_fid = (*env)->GetFieldID(env, file_class, "defineFn", "J");
    (*env)->SetLongField(env, file_object, define_fn_fid, (jlong)c_file.define_fn);

    jfieldID globals_size_fid = (*env)->GetFieldID(env, file_class, "globalsSize", "I");
    (*env)->SetIntField(env, file_object, globals_size_fid, (jint)c_file.globals_size);

    jfieldID init_globals_fn_fid = (*env)->GetFieldID(env, file_class, "initGlobalsFn", "J");
    (*env)->SetLongField(env, file_object, init_globals_fn_fid, (jlong)c_file.init_globals_fn);

    jfieldID define_type_fid = (*env)->GetFieldID(env, file_class, "defineType", "Ljava/lang/String;");
    jstring define_type = (*env)->NewStringUTF(env, c_file.define_type);
    (*env)->SetObjectField(env, file_object, define_type_fid, define_type);

    jfieldID on_fns_fid = (*env)->GetFieldID(env, file_class, "onFns", "J");
    (*env)->SetLongField(env, file_object, on_fns_fid, (jlong)c_file.on_fns);

    jfieldID resource_mtimes_fid = (*env)->GetFieldID(env, file_class, "resourceMtimes", "J");
    (*env)->SetLongField(env, file_object, resource_mtimes_fid, (jlong)c_file.resource_mtimes);
}

JNIEXPORT void JNICALL Java_game_Game_callInitGlobals(JNIEnv *env, jobject obj, jlong init_globals_fn, jbyteArray globals, jint entity_id) {
    (void)obj;

    jbyte *globals_bytes = (*env)->GetByteArrayElements(env, globals, NULL);

    ((grug_init_globals_fn_t)init_globals_fn)(globals_bytes, entity_id);

    (*env)->ReleaseByteArrayElements(env, globals, globals_bytes, 0);
}
"""

    output += "\n"
    output += "\n"
    output += "\n"
    output += "\n"
    output += "\n"
    output += "\n"
    output += "\n"
    output += "\n"
    output += "\n"
    output += "\n"
    output += "\n"
    output += "\n"
    output += "\n"
    output += "\n"
    output += "\n"
    output += "\n"
    output += "\n"
    output += "\n"
    output += "\n"
    output += "\n"
    output += "\n"
    output += "\n"

    pass
    pass
    pass
    pass
    pass

    for entity in mod_api["entities"].keys():
        output += f"static PyObject *game_fn_define_{entity}_handle;\n"

    for fn in mod_api["game_functions"].keys():
        output += f"static PyObject *game_fn_{fn}_handle;\n"

    output += "\n"

    output += "#define CHECK_PYTHON_ERROR() {\\\n"
    output += "    if (PyErr_Occurred()) {\\\n"
    output += "        PyErr_Print();\\\n"
    output += (
        '        fprintf(stderr, "Error detected in adapter.c:%d\\n", __LINE__);\\\n'
    )
    output += "        exit(EXIT_FAILURE);\\\n"
    output += "    }\\\n"
    output += "}\n"

    output += "\n"

    output += "void init(void) {\n"

    output += '    PyObject *modules = PySys_GetObject("modules");\n'
    output += "    CHECK_PYTHON_ERROR();\n"
    output += "    assert(modules);\n"

    output += "\n"

    output += '    main_module = PyDict_GetItemString(modules, "__main__");\n'
    output += "    CHECK_PYTHON_ERROR();\n"
    output += "    assert(main_module);\n"

    output += "\n"

    for entity in mod_api["entities"].keys():
        output += f'    game_fn_define_{entity}_handle = PyObject_GetAttrString(main_module, "game_fn_define_{entity}");\n'
        output += f"    CHECK_PYTHON_ERROR();\n"
        output += f"    assert(game_fn_define_{entity}_handle);\n"
        output += "\n"

    for i, fn in enumerate(mod_api["game_functions"].keys()):
        output += f'    game_fn_{fn}_handle = PyObject_GetAttrString(main_module, "game_fn_{fn}");\n'
        output += f"    CHECK_PYTHON_ERROR();\n"
        output += f"    assert(game_fn_{fn}_handle);\n"

        if i < len(mod_api["game_functions"].keys()) - 1:
            output += "\n"

    output += "}\n"

    output += "\n"

    for name, entity in mod_api["entities"].items():
        output += f"void game_fn_define_{name}("

        for i, field in enumerate(entity["fields"]):
            if i > 0:
                output += ", "

            output += field["type"]
            output += " "
            output += field["name"]

        output += ") {\n"

        arg_count = len(entity["fields"])

        if arg_count > 0:
            for field_index, field in enumerate(entity["fields"]):
                output += f"    PyObject *arg{field_index + 1} = "

                typ = field["type"]

                # TODO: Test all these!
                if typ == "bool" or typ == "i32":
                    output += "PyLong_FromLong"
                elif typ == "id":
                    output += "PyLong_FromUnsignedLongLong"
                elif typ == "f32":
                    output += "PyFloat_FromDouble"
                elif typ == "string" or typ == "resource" or typ == "entity":
                    output += "PyUnicode_FromString"

                output += "("
                output += field["name"]
                output += ");\n"

                output += "    CHECK_PYTHON_ERROR();\n"
                output += f"    assert(arg{field_index + 1});\n"

            output += "\n"

            output += f"    PyObject *args = PyTuple_Pack({arg_count}"

            for field_index in range(arg_count):
                output += f", arg{field_index + 1}"

            output += ");\n"

            output += "    CHECK_PYTHON_ERROR();\n"
            output += "    assert(args);\n"

            output += "\n"

        output += (
            f"    PyObject *result = PyObject_CallObject(game_fn_define_{name}_handle, "
        )
        output += "args" if arg_count > 0 else "NULL"
        output += ");\n"
        output += "    CHECK_PYTHON_ERROR();\n"
        output += "    assert(result);\n"

        output += "}\n"

        output += "\n"

    for i, (name, fn) in enumerate(mod_api["game_functions"].items()):
        output += fn.get("return_type", "void")

        output += f" game_fn_{name}("

        for arg_index, arg in enumerate(fn["arguments"]):
            if arg_index > 0:
                output += ", "

            output += arg["type"]
            output += " "
            output += arg["name"]

        output += ") {\n"

        arg_count = len(fn["arguments"])

        if arg_count > 0:
            for arg_index, arg in enumerate(fn["arguments"]):
                output += f"    PyObject *arg{arg_index + 1} = "

                typ = arg["type"]

                # TODO: Test all these!
                if typ == "bool" or typ == "i32":
                    output += "PyLong_FromLong"
                elif typ == "id":
                    output += "PyLong_FromUnsignedLongLong"
                elif typ == "f32":
                    output += "PyFloat_FromDouble"
                elif typ == "string" or typ == "resource" or typ == "entity":
                    output += "PyUnicode_FromString"

                output += "("
                output += arg["name"]
                output += ");\n"

                output += "    CHECK_PYTHON_ERROR();\n"
                output += f"    assert(arg{arg_index + 1});\n"

            output += "\n"

            output += f"    PyObject *args = PyTuple_Pack({arg_count}"

            for arg_index in range(arg_count):
                output += f", arg{arg_index + 1}"

            output += ");\n"

            output += "    CHECK_PYTHON_ERROR();\n"
            output += "    assert(args);\n"

            output += "\n"

        output += f"    PyObject *result = PyObject_CallObject(game_fn_{name}_handle, "
        output += "args" if arg_count > 0 else "NULL"
        output += ");\n"
        output += "    CHECK_PYTHON_ERROR();\n"
        output += "    assert(result);\n"

        if "return_type" in fn:
            return_type = fn["return_type"]

            output += "\n"

            # TODO: Test all these!
            if return_type == "bool" or return_type == "i32":
                output += "    return PyLong_AsLong(result);\n"
            elif return_type == "id":
                output += "    return PyLong_AsUnsignedLongLong(result);\n"
            elif return_type == "f32":
                output += "    return PyFloat_AsDouble(result);\n"
            elif (
                return_type == "string"
                or return_type == "resource"
                or return_type == "entity"
            ):
                output += "    return PyUnicode_AsUTF8(result);\n"

        output += "}\n"

        if i < len(mod_api["game_functions"].keys()) - 1:
            output += "\n"

    return output


def main(mod_api_path, output_path):
    with open(mod_api_path) as f:
        mod_api = json.load(f)

    with open(output_path, "w") as f:
        f.write(get_output(mod_api))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
