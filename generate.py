import json
import sys


def get_output(mod_api):
    output = """#include "headers/game_Game.h"

#include "grug/grug.h"

#include <assert.h>
#include <stdbool.h>
#include <stdio.h>

typedef char* string;
typedef int32_t i32;
typedef uint64_t id;
"""

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

    output += """
JNIEnv *global_env;
jobject global_obj;

jmethodID runtime_error_handler_id;
"""

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

    for fn_name, fn in mod_api["game_functions"].items():
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

        output += "\n"

    output += """void runtime_error_handler(char *reason, enum grug_runtime_error_type type, char *on_fn_name, char *on_fn_path) {
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

JNIEXPORT void JNICALL Java_game_Game_init(JNIEnv *env, jobject obj) {
    global_env = env;
    global_obj = obj;

    jclass javaClass = (*env)->GetObjectClass(env, obj);
    assert(javaClass);

    runtime_error_handler_id = (*env)->GetMethodID(env, javaClass, "runtimeErrorHandler", "(Ljava/lang/String;ILjava/lang/String;Ljava/lang/String;)V");
    assert(runtime_error_handler_id);

    jclass entity_definitions_class = (*env)->FindClass(env, "game/EntityDefinitions");
    assert(entity_definitions_class);
"""

    # TODO: Add the rest of Java_game_Game_init()

    output += "}\n"

    output += """
JNIEXPORT void JNICALL Java_game_Game_fillRootGrugDir(JNIEnv *env, jobject obj, jobject dir_object) {
    (void)obj;

    jclass dir_class = (*env)->GetObjectClass(env, dir_object);

    jfieldID name_fid = (*env)->GetFieldID(env, dir_class, "name", "Ljava/lang/String;");
    jstring name = (*env)->NewStringUTF(env, grug_mods.name);
    (*env)->SetObjectField(env, dir_object, name_fid, name);

    jfieldID dirs_size_fid = (*env)->GetFieldID(env, dir_class, "dirsSize", "I");
    (*env)->SetIntField(env, dir_object, dirs_size_fid, (jint)grug_mods.dirs_size);

    jfieldID files_size_fid = (*env)->GetFieldID(env, dir_class, "filesSize", "I");
    (*env)->SetIntField(env, dir_object, files_size_fid, (jint)grug_mods.files_size);

    jfieldID address_fid = (*env)->GetFieldID(env, dir_class, "address", "J");
    (*env)->SetLongField(env, dir_object, address_fid, (jlong)&grug_mods);
}

JNIEXPORT void JNICALL Java_game_Game_fillGrugDir(JNIEnv *env, jobject obj, jobject dir_object, jlong parent_dir_address, jint dir_index) {
    (void)obj;

    jclass dir_class = (*env)->GetObjectClass(env, dir_object);

    struct grug_mod_dir *parent_dir = (struct grug_mod_dir *)parent_dir_address;

    struct grug_mod_dir dir = parent_dir->dirs[dir_index];

    jfieldID name_fid = (*env)->GetFieldID(env, dir_class, "name", "Ljava/lang/String;");
    jstring name = (*env)->NewStringUTF(env, dir.name);
    (*env)->SetObjectField(env, dir_object, name_fid, name);

    jfieldID dirs_size_fid = (*env)->GetFieldID(env, dir_class, "dirsSize", "I");
    (*env)->SetIntField(env, dir_object, dirs_size_fid, (jint)dir.dirs_size);

    jfieldID files_size_fid = (*env)->GetFieldID(env, dir_class, "filesSize", "I");
    (*env)->SetIntField(env, dir_object, files_size_fid, (jint)dir.files_size);

    jfieldID address_fid = (*env)->GetFieldID(env, dir_class, "address", "J");
    (*env)->SetLongField(env, dir_object, address_fid, (jlong)&parent_dir->dirs[dir_index]);
}

JNIEXPORT void JNICALL Java_game_Game_fillGrugFile(JNIEnv *env, jobject obj, jobject file_object, jlong parent_dir_address, jint file_index) {
    (void)obj;

    jclass file_class = (*env)->GetObjectClass(env, file_object);

    struct grug_mod_dir *parent_dir = (struct grug_mod_dir *)parent_dir_address;

    struct grug_file file = parent_dir->files[file_index];

    jfieldID name_fid = (*env)->GetFieldID(env, file_class, "name", "Ljava/lang/String;");
    jstring name = (*env)->NewStringUTF(env, file.name);
    (*env)->SetObjectField(env, file_object, name_fid, name);

    jfieldID dll_fid = (*env)->GetFieldID(env, file_class, "dll", "J");
    (*env)->SetLongField(env, file_object, dll_fid, (jlong)file.dll);

    jfieldID define_fn_fid = (*env)->GetFieldID(env, file_class, "defineFn", "J");
    (*env)->SetLongField(env, file_object, define_fn_fid, (jlong)file.define_fn);

    jfieldID globals_size_fid = (*env)->GetFieldID(env, file_class, "globalsSize", "I");
    (*env)->SetIntField(env, file_object, globals_size_fid, (jint)file.globals_size);

    jfieldID init_globals_fn_fid = (*env)->GetFieldID(env, file_class, "initGlobalsFn", "J");
    (*env)->SetLongField(env, file_object, init_globals_fn_fid, (jlong)file.init_globals_fn);

    jfieldID define_type_fid = (*env)->GetFieldID(env, file_class, "defineType", "Ljava/lang/String;");
    jstring define_type = (*env)->NewStringUTF(env, file.define_type);
    (*env)->SetObjectField(env, file_object, define_type_fid, define_type);

    jfieldID on_fns_fid = (*env)->GetFieldID(env, file_class, "onFns", "J");
    (*env)->SetLongField(env, file_object, on_fns_fid, (jlong)file.on_fns);

    jfieldID resource_mtimes_fid = (*env)->GetFieldID(env, file_class, "resourceMtimes", "J");
    (*env)->SetLongField(env, file_object, resource_mtimes_fid, (jlong)file.resource_mtimes);
}

JNIEXPORT void JNICALL Java_game_Game_callDefineFn(JNIEnv *env, jobject obj, jlong define_fn) {
    (void)env;
    (void)obj;

    ((grug_define_fn_t)define_fn)();
}

JNIEXPORT void JNICALL Java_game_Game_toggleOnFnsMode(JNIEnv *env, jobject obj) {
    (void)env;
    (void)obj;

    grug_toggle_on_fns_mode();
}

JNIEXPORT jboolean JNICALL Java_game_Game_areOnFnsInSafeMode(JNIEnv *env, jobject obj) {
    (void)env;
    (void)obj;

    return grug_are_on_fns_in_safe_mode();
}
"""

    output += "\n"

    return output


def main(mod_api_path, output_path):
    with open(mod_api_path) as f:
        mod_api = json.load(f)

    with open(output_path, "w") as f:
        f.write(get_output(mod_api))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
