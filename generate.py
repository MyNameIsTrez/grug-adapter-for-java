import json
import sys


def get_output(mod_api, package_slash, grug_class):
    package_underscore = package_slash.replace("/", "_")

    output = """#include <jni.h>

#include "grug/grug.h"

#include <assert.h>
#include <stdbool.h>
#include <stdio.h>

typedef char* string;
typedef int32_t i32;
typedef uint64_t id;

#ifdef DONT_ASSERT_JNI
#define ASSERT_JNI(obj, env)
#else
#define ASSERT_JNI(obj, env) {\\
    if (obj == NULL) {\\
        (*env)->ExceptionDescribe(env);\\
        exit(EXIT_FAILURE);\\
    }\\
}
#endif
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

    for entity_name, entity in mod_api["entities"].items():
        output += f"void game_fn_define_{entity_name}("

        for field_index, field in enumerate(entity["fields"]):
            if field_index > 0:
                output += ", "

            output += f"{field["type"]} c_{field["name"]}"

        output += ") {\n"

        for field_index, field in enumerate(entity["fields"]):
            field_name = field["name"]

            if field_index > 0:
                output += "\n"

            if field["type"] == "string":
                output += f"    jstring {field_name} = (*global_env)->NewStringUTF(global_env, c_{field_name});\n"
                output += f"    ASSERT_JNI({field_name}, global_env);\n"
                output += f"    (*global_env)->SetObjectField(global_env, {entity_name}_definition_obj, {entity_name}_definition_{field_name}_fid, {field_name});\n"
            elif field["type"] == "i32":
                output += f"    (*global_env)->SetIntField(global_env, {entity_name}_definition_obj, {entity_name}_definition_{field_name}_fid, c_{field_name});\n"
            else:
                # TODO: Support more types
                assert False

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

    output += f"""void runtime_error_handler(char *reason, enum grug_runtime_error_type type, char *on_fn_name, char *on_fn_path) {{
    jstring java_reason = (*global_env)->NewStringUTF(global_env, reason);
    ASSERT_JNI(java_reason, global_env);
    jint java_type = type;
    jstring java_on_fn_name = (*global_env)->NewStringUTF(global_env, on_fn_name);
    ASSERT_JNI(java_on_fn_name, global_env);
    jstring java_on_fn_path = (*global_env)->NewStringUTF(global_env, on_fn_path);
    ASSERT_JNI(java_on_fn_path, global_env);

    (*global_env)->CallVoidMethod(global_env, global_obj, runtime_error_handler_id, java_reason, java_type, java_on_fn_name, java_on_fn_path);
}}

JNIEXPORT void JNICALL Java_{package_underscore}_{grug_class}_grugSetRuntimeErrorHandler(JNIEnv *env, jobject obj) {{
    (void)env;
    (void)obj;

    grug_set_runtime_error_handler(runtime_error_handler);
}}

JNIEXPORT jboolean JNICALL Java_{package_underscore}_{grug_class}_errorHasChanged(JNIEnv *env, jobject obj) {{
    (void)env;
    (void)obj;

    return grug_error.has_changed;
}}

JNIEXPORT jboolean JNICALL Java_{package_underscore}_{grug_class}_loadingErrorInGrugFile(JNIEnv *env, jobject obj) {{
    (void)env;
    (void)obj;

    return grug_loading_error_in_grug_file;
}}

JNIEXPORT jstring JNICALL Java_{package_underscore}_{grug_class}_errorMsg(JNIEnv *env, jobject obj) {{
    (void)env;
    (void)obj;

    return (*global_env)->NewStringUTF(global_env, grug_error.msg);
}}

JNIEXPORT jstring JNICALL Java_{package_underscore}_{grug_class}_errorPath(JNIEnv *env, jobject obj) {{
    (void)env;
    (void)obj;

    return (*global_env)->NewStringUTF(global_env, grug_error.path);
}}

JNIEXPORT jstring JNICALL Java_{package_underscore}_{grug_class}_onFnName(JNIEnv *env, jobject obj) {{
    (void)env;
    (void)obj;

    return (*global_env)->NewStringUTF(global_env, grug_on_fn_name);
}}

JNIEXPORT jstring JNICALL Java_{package_underscore}_{grug_class}_onFnPath(JNIEnv *env, jobject obj) {{
    (void)env;
    (void)obj;

    return (*global_env)->NewStringUTF(global_env, grug_on_fn_path);
}}

JNIEXPORT jint JNICALL Java_{package_underscore}_{grug_class}_errorGrugCLineNumber(JNIEnv *env, jobject obj) {{
    (void)env;
    (void)obj;

    return grug_error.grug_c_line_number;
}}

JNIEXPORT jboolean JNICALL Java_{package_underscore}_{grug_class}_grugRegenerateModifiedMods(JNIEnv *env, jobject obj) {{
    (void)env;
    (void)obj;

    return grug_regenerate_modified_mods();
}}

JNIEXPORT jint JNICALL Java_{package_underscore}_{grug_class}_getGrugReloadsSize(JNIEnv *env, jobject obj) {{
    (void)env;
    (void)obj;

    return grug_reloads_size;
}}

JNIEXPORT void JNICALL Java_{package_underscore}_{grug_class}_fillReloadData(JNIEnv *env, jobject obj, jobject reload_data_object, jint reload_index) {{
    (void)obj;

    struct grug_modified c_reload_data = grug_reloads[reload_index];

    jclass reload_data_class = (*env)->GetObjectClass(env, reload_data_object);

    jfieldID path_fid = (*env)->GetFieldID(env, reload_data_class, "path", "Ljava/lang/String;");
    ASSERT_JNI(path_fid, env);
    jstring path = (*env)->NewStringUTF(env, c_reload_data.path);
    ASSERT_JNI(path, env);
    (*env)->SetObjectField(env, reload_data_object, path_fid, path);

    jfieldID old_dll_fid = (*env)->GetFieldID(env, reload_data_class, "oldDll", "J");
    ASSERT_JNI(old_dll_fid, env);
    (*env)->SetLongField(env, reload_data_object, old_dll_fid, (jlong)c_reload_data.old_dll);

    jfieldID file_fid = (*env)->GetFieldID(env, reload_data_class, "file", "L{package_slash}/GrugFile;");
    ASSERT_JNI(file_fid, env);
    jobject file_object = (*env)->GetObjectField(env, reload_data_object, file_fid);

    jclass file_class = (*env)->GetObjectClass(env, file_object);

    struct grug_file c_file = c_reload_data.file;

    jfieldID name_fid = (*env)->GetFieldID(env, file_class, "name", "Ljava/lang/String;");
    ASSERT_JNI(name_fid, env);
    jstring name = (*env)->NewStringUTF(env, c_file.name);
    ASSERT_JNI(name, env);
    (*env)->SetObjectField(env, file_object, name_fid, name);

    jfieldID dll_fid = (*env)->GetFieldID(env, file_class, "dll", "J");
    ASSERT_JNI(dll_fid, env);
    (*env)->SetLongField(env, file_object, dll_fid, (jlong)c_file.dll);

    jfieldID define_fn_fid = (*env)->GetFieldID(env, file_class, "defineFn", "J");
    ASSERT_JNI(define_fn_fid, env);
    (*env)->SetLongField(env, file_object, define_fn_fid, (jlong)c_file.define_fn);

    jfieldID globals_size_fid = (*env)->GetFieldID(env, file_class, "globalsSize", "I");
    ASSERT_JNI(globals_size_fid, env);
    (*env)->SetIntField(env, file_object, globals_size_fid, (jint)c_file.globals_size);

    jfieldID init_globals_fn_fid = (*env)->GetFieldID(env, file_class, "initGlobalsFn", "J");
    ASSERT_JNI(init_globals_fn_fid, env);
    (*env)->SetLongField(env, file_object, init_globals_fn_fid, (jlong)c_file.init_globals_fn);

    jfieldID define_type_fid = (*env)->GetFieldID(env, file_class, "defineType", "Ljava/lang/String;");
    ASSERT_JNI(define_type_fid, env);
    jstring define_type = (*env)->NewStringUTF(env, c_file.define_type);
    ASSERT_JNI(define_type, env);
    (*env)->SetObjectField(env, file_object, define_type_fid, define_type);

    jfieldID on_fns_fid = (*env)->GetFieldID(env, file_class, "onFns", "J");
    ASSERT_JNI(on_fns_fid, env);
    (*env)->SetLongField(env, file_object, on_fns_fid, (jlong)c_file.on_fns);

    jfieldID resource_mtimes_fid = (*env)->GetFieldID(env, file_class, "resourceMtimes", "J");
    ASSERT_JNI(resource_mtimes_fid, env);
    (*env)->SetLongField(env, file_object, resource_mtimes_fid, (jlong)c_file.resource_mtimes);
}}

JNIEXPORT void JNICALL Java_{package_underscore}_{grug_class}_callInitGlobals(JNIEnv *env, jobject obj, jlong init_globals_fn, jbyteArray globals, jint entity_id) {{
    (void)obj;

    jbyte *globals_bytes = (*env)->GetByteArrayElements(env, globals, NULL);
    ASSERT_JNI(globals_bytes, env);

    ((grug_init_globals_fn_t)init_globals_fn)(globals_bytes, entity_id);

    (*env)->ReleaseByteArrayElements(env, globals, globals_bytes, 0);
}}

JNIEXPORT void JNICALL Java_{package_underscore}_{grug_class}_init(JNIEnv *env, jobject obj) {{
    global_env = env;
    global_obj = obj;

    jclass javaClass = (*env)->GetObjectClass(env, obj);

    runtime_error_handler_id = (*env)->GetMethodID(env, javaClass, "runtimeErrorHandler", "(Ljava/lang/String;ILjava/lang/String;Ljava/lang/String;)V");
    ASSERT_JNI(runtime_error_handler_id, env);

    jclass entity_definitions_class = (*env)->FindClass(env, "{package_slash}/EntityDefinitions");
    ASSERT_JNI(entity_definitions_class, env);
"""

    output += "\n"

    for entity_name, entity in mod_api["entities"].items():
        output += f'    jfieldID {entity_name}_definition_fid = (*env)->GetStaticFieldID(env, entity_definitions_class, "{entity_name}", "L{package_slash}/{snake_to_pascal(entity_name)};");\n'
        output += f'    ASSERT_JNI({entity_name}_definition_fid, env);\n'

        output += "\n"

        output += f"    {entity_name}_definition_obj = (*env)->GetStaticObjectField(env, entity_definitions_class, {entity_name}_definition_fid);\n"

        output += "\n"

        output += f"    {entity_name}_definition_obj = (*env)->NewGlobalRef(env, {entity_name}_definition_obj);\n"

        output += "\n"

        if len(entity["fields"]) > 0:
            output += f"    jclass {entity_name}_definition_class = (*env)->GetObjectClass(env, {entity_name}_definition_obj);\n"

            output += "\n"

        for field in entity["fields"]:
            field_name = field["name"]
            field_type = field["type"]

            output += f'    {entity_name}_definition_{field_name}_fid = (*env)->GetFieldID(env, {entity_name}_definition_class, "{snake_to_camel(field_name)}", "'

            output += get_signature_type(field_type)

            output += '");\n'

            output += f'    ASSERT_JNI({entity_name}_definition_{field_name}_fid, env);\n'

            output += "\n"

    for fn_index, (fn_name, fn) in enumerate(mod_api["game_functions"].items()):
        if fn_index > 0:
            output += "\n"

        output += f'    game_fn_{fn_name}_id = (*env)->GetMethodID(env, javaClass, "gameFn_{snake_to_camel(fn_name)}", "('

        for argument in fn["arguments"]:
            output += get_signature_type(argument["type"])

        output += ")"

        output += get_signature_type(fn["return_type"]) if "return_type" in fn else "V"

        output += '");\n'

        output += f'    ASSERT_JNI(game_fn_{fn_name}_id, env);\n'

    output += "}\n"

    output += f"""
JNIEXPORT void JNICALL Java_{package_underscore}_{grug_class}_fillRootGrugDir(JNIEnv *env, jobject obj, jobject dir_object) {{
    (void)obj;

    jclass dir_class = (*env)->GetObjectClass(env, dir_object);

    jfieldID name_fid = (*env)->GetFieldID(env, dir_class, "name", "Ljava/lang/String;");
    ASSERT_JNI(name_fid, env);
    jstring name = (*env)->NewStringUTF(env, grug_mods.name);
    ASSERT_JNI(name, env);
    (*env)->SetObjectField(env, dir_object, name_fid, name);

    jfieldID dirs_size_fid = (*env)->GetFieldID(env, dir_class, "dirsSize", "I");
    ASSERT_JNI(dirs_size_fid, env);
    (*env)->SetIntField(env, dir_object, dirs_size_fid, (jint)grug_mods.dirs_size);

    jfieldID files_size_fid = (*env)->GetFieldID(env, dir_class, "filesSize", "I");
    ASSERT_JNI(files_size_fid, env);
    (*env)->SetIntField(env, dir_object, files_size_fid, (jint)grug_mods.files_size);

    jfieldID address_fid = (*env)->GetFieldID(env, dir_class, "address", "J");
    ASSERT_JNI(address_fid, env);
    (*env)->SetLongField(env, dir_object, address_fid, (jlong)&grug_mods);
}}

JNIEXPORT void JNICALL Java_{package_underscore}_{grug_class}_fillGrugDir(JNIEnv *env, jobject obj, jobject dir_object, jlong parent_dir_address, jint dir_index) {{
    (void)obj;

    jclass dir_class = (*env)->GetObjectClass(env, dir_object);

    struct grug_mod_dir *parent_dir = (struct grug_mod_dir *)parent_dir_address;

    struct grug_mod_dir dir = parent_dir->dirs[dir_index];

    jfieldID name_fid = (*env)->GetFieldID(env, dir_class, "name", "Ljava/lang/String;");
    ASSERT_JNI(name_fid, env);
    jstring name = (*env)->NewStringUTF(env, dir.name);
    ASSERT_JNI(name, env);
    (*env)->SetObjectField(env, dir_object, name_fid, name);

    jfieldID dirs_size_fid = (*env)->GetFieldID(env, dir_class, "dirsSize", "I");
    ASSERT_JNI(dirs_size_fid, env);
    (*env)->SetIntField(env, dir_object, dirs_size_fid, (jint)dir.dirs_size);

    jfieldID files_size_fid = (*env)->GetFieldID(env, dir_class, "filesSize", "I");
    ASSERT_JNI(files_size_fid, env);
    (*env)->SetIntField(env, dir_object, files_size_fid, (jint)dir.files_size);

    jfieldID address_fid = (*env)->GetFieldID(env, dir_class, "address", "J");
    ASSERT_JNI(address_fid, env);
    (*env)->SetLongField(env, dir_object, address_fid, (jlong)&parent_dir->dirs[dir_index]);
}}

JNIEXPORT void JNICALL Java_{package_underscore}_{grug_class}_fillGrugFile(JNIEnv *env, jobject obj, jobject file_object, jlong parent_dir_address, jint file_index) {{
    (void)obj;

    jclass file_class = (*env)->GetObjectClass(env, file_object);

    struct grug_mod_dir *parent_dir = (struct grug_mod_dir *)parent_dir_address;

    struct grug_file file = parent_dir->files[file_index];

    jfieldID name_fid = (*env)->GetFieldID(env, file_class, "name", "Ljava/lang/String;");
    ASSERT_JNI(name_fid, env);
    jstring name = (*env)->NewStringUTF(env, file.name);
    ASSERT_JNI(name, env);
    (*env)->SetObjectField(env, file_object, name_fid, name);

    jfieldID dll_fid = (*env)->GetFieldID(env, file_class, "dll", "J");
    ASSERT_JNI(dll_fid, env);
    (*env)->SetLongField(env, file_object, dll_fid, (jlong)file.dll);

    jfieldID define_fn_fid = (*env)->GetFieldID(env, file_class, "defineFn", "J");
    ASSERT_JNI(define_fn_fid, env);
    (*env)->SetLongField(env, file_object, define_fn_fid, (jlong)file.define_fn);

    jfieldID globals_size_fid = (*env)->GetFieldID(env, file_class, "globalsSize", "I");
    ASSERT_JNI(globals_size_fid, env);
    (*env)->SetIntField(env, file_object, globals_size_fid, (jint)file.globals_size);

    jfieldID init_globals_fn_fid = (*env)->GetFieldID(env, file_class, "initGlobalsFn", "J");
    ASSERT_JNI(init_globals_fn_fid, env);
    (*env)->SetLongField(env, file_object, init_globals_fn_fid, (jlong)file.init_globals_fn);

    jfieldID define_type_fid = (*env)->GetFieldID(env, file_class, "defineType", "Ljava/lang/String;");
    ASSERT_JNI(define_type_fid, env);
    jstring define_type = (*env)->NewStringUTF(env, file.define_type);
    ASSERT_JNI(define_type, env);
    (*env)->SetObjectField(env, file_object, define_type_fid, define_type);

    jfieldID on_fns_fid = (*env)->GetFieldID(env, file_class, "onFns", "J");
    ASSERT_JNI(on_fns_fid, env);
    (*env)->SetLongField(env, file_object, on_fns_fid, (jlong)file.on_fns);

    jfieldID resource_mtimes_fid = (*env)->GetFieldID(env, file_class, "resourceMtimes", "J");
    ASSERT_JNI(resource_mtimes_fid, env);
    (*env)->SetLongField(env, file_object, resource_mtimes_fid, (jlong)file.resource_mtimes);
}}

JNIEXPORT void JNICALL Java_{package_underscore}_{grug_class}_callDefineFn(JNIEnv *env, jobject obj, jlong define_fn) {{
    (void)env;
    (void)obj;

    ((grug_define_fn_t)define_fn)();
}}

JNIEXPORT void JNICALL Java_{package_underscore}_{grug_class}_toggleOnFnsMode(JNIEnv *env, jobject obj) {{
    (void)env;
    (void)obj;

    grug_toggle_on_fns_mode();
}}

JNIEXPORT jboolean JNICALL Java_{package_underscore}_{grug_class}_areOnFnsInSafeMode(JNIEnv *env, jobject obj) {{
    (void)env;
    (void)obj;

    return grug_are_on_fns_in_safe_mode();
}}
"""

    output += "\n"

    for entity_name, entity in mod_api["entities"].items():
        if "on_functions" not in entity:
            continue

        for on_fn_name, on_fn in entity["on_functions"].items():
            output += f"JNIEXPORT jboolean JNICALL Java_{package_underscore}_{grug_class}_{entity_name}_1has_1{snake_to_camel(on_fn_name)}(JNIEnv *env, jobject obj, jlong on_fns) {{\n"

            output += f"""    (void)env;
    (void)obj;

    return ((struct {entity_name}_on_fns *)on_fns)->{on_fn_name} != NULL;
"""

            output += "}\n"

            output += "\n"

            output += f"JNIEXPORT void JNICALL Java_{package_underscore}_{grug_class}_{entity_name}_1{snake_to_camel(on_fn_name)}(JNIEnv *env, jobject obj, jlong on_fns, jbyteArray globals) {{\n"

            output += f"""    (void)obj;

    jbyte *globals_bytes = (*env)->GetByteArrayElements(env, globals, NULL);
    ASSERT_JNI(globals_bytes, env);

    ((struct {entity_name}_on_fns *)on_fns)->{on_fn_name}(globals_bytes);

    (*env)->ReleaseByteArrayElements(env, globals, globals_bytes, 0);
"""

            output += "}\n"

    return output


# Converts snake_case to camelCase
# Source: https://stackoverflow.com/a/70999330/13279557
def snake_to_camel(s):
    return s[0] + s.title().replace("_", "")[1:]


# Converts snake_case to PascalCase
def snake_to_pascal(s):
    return s.title().replace("_", "")


# From the "Type Signatures" header here:
# https://docs.oracle.com/javase/8/docs/technotes/guides/jni/spec/types.html
def get_signature_type(typ):
    if typ == "i32" or typ == "id":
        return "I"
    elif typ == "string":
        return "Ljava/lang/String;"

    # TODO: Support more types
    assert False


def main(mod_api_path, output_path, package_slash, grug_class):
    with open(mod_api_path) as f:
        mod_api = json.load(f)

    with open(output_path, "w") as f:
        f.write(get_output(mod_api, package_slash, grug_class))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
