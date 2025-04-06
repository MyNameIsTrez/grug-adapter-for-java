import json
import sys


def get_output(mod_api, package_slash, grug_class):
    package_underscore = package_slash.replace("/", "_")

    output = """// THIS FILE WAS GENERATED BY grug-adapter-for-java, SO DON'T EDIT IT!

#include <jni.h>

#include "grug/grug.h"

#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

typedef char* string;
typedef int32_t i32;
typedef float f32;
typedef uint64_t id;

#ifdef DONT_CHECK_EXCEPTIONS
#define CHECK(env)

#define CHECK_NEW_GLOBAL_REF(result)
#else
#define CHECK(env) {\\
    if ((*env)->ExceptionCheck(env)) {\\
        fprintf(stderr, "Exception detected at %s:%d\\n", __FILE__, __LINE__);\\
        (*env)->ExceptionDescribe(env);\\
        exit(EXIT_FAILURE);\\
    }\\
}

#define CHECK_NEW_GLOBAL_REF(result) {\\
    if (result == NULL) {\\
        fprintf(stderr, "NewGlobalRef() error detected at %s:%d\\n", __FILE__, __LINE__);\\
        exit(EXIT_FAILURE);\\
    }\\
}
#endif

// > Do not save instances of JNIEnv* unless you are sure they will be referenced in the same thread.
// From https://stackoverflow.com/a/23963070/13279557
// > The main takeaway from this is "don't cache JNIEnv".
// From https://stackoverflow.com/a/16843011/13279557
#define FILL_ENV(env) {\\
    jint result = (*jvm)->GetEnv(jvm, (void**)&env, jni_version);\\
    if (result != JNI_OK) {\\
        fprintf(stderr, "GetEnv failed with result %d in %s:%d\\n", result, __FILE__, __LINE__);\\
        exit(EXIT_FAILURE);\\
    }\\
}

// This indicates something can't be made static,
// since the value is shared between the two opened libadapter.so instances:
// One that Java uses to call native C functions,
// and one with RTLD_GLOBAL that mods use to find the game function bindings
#define not_static
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
not_static jint jni_version;
not_static JavaVM* jvm;

not_static jobject grug_object;

not_static jclass game_functions_class;

not_static jmethodID runtime_error_handler_id;
"""

    output += "\n"

    for name in mod_api["game_functions"].keys():
        output += f"not_static jmethodID game_fn_{name}_id;\n"

    output += "\n"

    for fn_name, fn in mod_api["game_functions"].items():
        if "return_type" not in fn:
            output += "void "
        elif fn["return_type"] == "string":
            output += "const char *"
        else:
            output += fn["return_type"] + " "

        output += f"game_fn_{fn_name}("

        if "arguments" in fn:
            for argument_index, argument in enumerate(fn["arguments"]):
                if argument_index > 0:
                    output += ", "

                output += f"{argument["type"]} "

                if (
                    argument["type"] == "string"
                    or argument["type"] == "i32"
                    or argument["type"] == "f32"
                    or argument["type"] == "id"
                    or argument["type"] == "bool"
                ):
                    output += "c_"
                else:
                    # TODO: Support more types
                    assert False

                output += f"{argument["name"]}"

        output += f""") {{
    JNIEnv *env;
    FILL_ENV(env);
"""

        if "arguments" in fn:
            for argument_index, argument in enumerate(fn["arguments"]):
                argument_name = argument["name"]

                if argument_index > 0:
                    output += "\n"

                if argument["type"] == "string":
                    output += f"    jstring java_{argument_name} = (*env)->NewStringUTF(env, c_{argument_name});\n"
                    output += f"    CHECK(env);\n"
                elif argument["type"] == "i32" or argument["type"] == "f32" or argument["type"] == "id" or argument["type"] == "bool":
                    pass
                else:
                    # TODO: Support more types
                    assert False

        output += "\n"
        output += "    "

        if "return_type" in fn:
            if fn["return_type"] == "string":
                output += "jstring"
            elif fn["return_type"] == "i32":
                output += "jint"
            elif fn["return_type"] == "f32":
                output += "jfloat"
            elif fn["return_type"] == "id":
                output += "jlong"
            elif fn["return_type"] == "bool":
                output += "jboolean"
            else:
                # TODO: Support more types
                assert False

            output += " result = "

        output += "(*env)->CallStatic"

        if "return_type" not in fn:
            output += "Void"
        elif fn["return_type"] == "string":
            output += "Object"
        elif fn["return_type"] == "i32":
            output += "Int"
        elif fn["return_type"] == "f32":
            output += "Float"
        elif fn["return_type"] == "id":
            output += "Long"
        elif fn["return_type"] == "bool":
            output += "Boolean"
        else:
            # TODO: Support more types
            assert False

        output += f"Method(env, game_functions_class, game_fn_{fn_name}_id"

        if "arguments" in fn:
            for argument_index, argument in enumerate(fn["arguments"]):
                output += ", "

                if argument["type"] == "string":
                    output += "java_"
                elif argument["type"] == "i32" or argument["type"] == "f32" or argument["type"] == "id" or argument["type"] == "bool":
                    output += "c_"
                else:
                    # TODO: Support more types
                    assert False

                output += argument["name"]

        output += ");\n"

        output += "    CHECK(env);\n"

        if "return_type" in fn:
            output += "\n"
            output += "    return "
            if fn["return_type"] == "string":
                # TODO:
                # Right now this leaks memory
                # The tricky part is figuring out a way to call ReleaseStringUTFChars(),
                # or strdup() + free(), correctly so that the string can be used in global and local grug scope
                output += "(*env)->GetStringUTFChars(env, result, NULL)"
            else:
                output += "result"
            output += ";\n"

        output += "}\n"

        output += "\n"

    output += f"""void runtime_error_handler(char *c_reason, enum grug_runtime_error_type java_type, char *c_on_fn_name, char *c_on_fn_path) {{
    JNIEnv *env;
    FILL_ENV(env);

    jstring java_reason = (*env)->NewStringUTF(env, c_reason);
    CHECK(env);

    jstring java_on_fn_name = (*env)->NewStringUTF(env, c_on_fn_name);
    CHECK(env);

    jstring java_on_fn_path = (*env)->NewStringUTF(env, c_on_fn_path);
    CHECK(env);

    (*env)->CallVoidMethod(env, grug_object, runtime_error_handler_id, java_reason, java_type, java_on_fn_name, java_on_fn_path);
    CHECK(env);
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
    (void)obj;

    return (*env)->NewStringUTF(env, grug_error.msg);
}}

JNIEXPORT jstring JNICALL Java_{package_underscore}_{grug_class}_errorPath(JNIEnv *env, jobject obj) {{
    (void)obj;

    return (*env)->NewStringUTF(env, grug_error.path);
}}

JNIEXPORT jstring JNICALL Java_{package_underscore}_{grug_class}_fnName(JNIEnv *env, jobject obj) {{
    (void)obj;

    return (*env)->NewStringUTF(env, grug_fn_name);
}}

JNIEXPORT jstring JNICALL Java_{package_underscore}_{grug_class}_fnPath(JNIEnv *env, jobject obj) {{
    (void)obj;

    return (*env)->NewStringUTF(env, grug_fn_path);
}}

JNIEXPORT jint JNICALL Java_{package_underscore}_{grug_class}_errorGrugCLineNumber(JNIEnv *env, jobject obj) {{
    (void)env;
    (void)obj;

    return grug_error.grug_c_line_number;
}}

JNIEXPORT jboolean JNICALL Java_{package_underscore}_{grug_class}_grugInit(JNIEnv *env, jobject obj, jstring java_mod_api_json_path, jstring java_mods_dir_path) {{
    (void)obj;

    const char *c_mod_api_json_path = (*env)->GetStringUTFChars(env, java_mod_api_json_path, NULL);
    CHECK(env);

    const char *c_mods_dir_path = (*env)->GetStringUTFChars(env, java_mods_dir_path, NULL);
    CHECK(env);

    bool result = grug_init(runtime_error_handler, (char *)c_mod_api_json_path, (char *)c_mods_dir_path);

    (*env)->ReleaseStringUTFChars(env, java_mod_api_json_path, c_mod_api_json_path);
    (*env)->ReleaseStringUTFChars(env, java_mods_dir_path, c_mods_dir_path);

    return result;
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
    CHECK(env);
    jstring path = (*env)->NewStringUTF(env, c_reload_data.path);
    CHECK(env);
    (*env)->SetObjectField(env, reload_data_object, path_fid, path);

    jfieldID old_dll_fid = (*env)->GetFieldID(env, reload_data_class, "oldDll", "J");
    CHECK(env);
    (*env)->SetLongField(env, reload_data_object, old_dll_fid, (jlong)c_reload_data.old_dll);

    jfieldID file_fid = (*env)->GetFieldID(env, reload_data_class, "file", "L{package_slash}/GrugFile;");
    CHECK(env);
    jobject file_object = (*env)->GetObjectField(env, reload_data_object, file_fid);

    jclass file_class = (*env)->GetObjectClass(env, file_object);

    struct grug_file c_file = c_reload_data.file;

    jfieldID name_fid = (*env)->GetFieldID(env, file_class, "name", "Ljava/lang/String;");
    CHECK(env);
    jstring name = (*env)->NewStringUTF(env, c_file.name);
    CHECK(env);
    (*env)->SetObjectField(env, file_object, name_fid, name);

    jfieldID entity_fid = (*env)->GetFieldID(env, file_class, "entity", "Ljava/lang/String;");
    CHECK(env);
    jstring entity = (*env)->NewStringUTF(env, c_file.entity);
    CHECK(env);
    (*env)->SetObjectField(env, file_object, entity_fid, entity);

    jfieldID entity_type_fid = (*env)->GetFieldID(env, file_class, "entityType", "Ljava/lang/String;");
    CHECK(env);
    jstring entity_type = (*env)->NewStringUTF(env, c_file.entity_type);
    CHECK(env);
    (*env)->SetObjectField(env, file_object, entity_type_fid, entity_type);

    jfieldID dll_fid = (*env)->GetFieldID(env, file_class, "dll", "J");
    CHECK(env);
    (*env)->SetLongField(env, file_object, dll_fid, (jlong)c_file.dll);

    jfieldID globals_size_fid = (*env)->GetFieldID(env, file_class, "globalsSize", "I");
    CHECK(env);
    (*env)->SetIntField(env, file_object, globals_size_fid, (jint)c_file.globals_size);

    jfieldID init_globals_fn_fid = (*env)->GetFieldID(env, file_class, "initGlobalsFn", "J");
    CHECK(env);
    (*env)->SetLongField(env, file_object, init_globals_fn_fid, (jlong)c_file.init_globals_fn);

    jfieldID on_fns_fid = (*env)->GetFieldID(env, file_class, "onFns", "J");
    CHECK(env);
    (*env)->SetLongField(env, file_object, on_fns_fid, (jlong)c_file.on_fns);

    jfieldID resource_mtimes_fid = (*env)->GetFieldID(env, file_class, "resourceMtimes", "J");
    CHECK(env);
    (*env)->SetLongField(env, file_object, resource_mtimes_fid, (jlong)c_file.resource_mtimes);
}}

JNIEXPORT void JNICALL Java_{package_underscore}_{grug_class}_callInitGlobals(JNIEnv *env, jobject obj, jlong init_globals_fn, jbyteArray globals, jlong entity_id) {{
    (void)obj;

    jbyte *globals_bytes = (*env)->GetByteArrayElements(env, globals, NULL);
    CHECK(env);

    ((grug_init_globals_fn_t)init_globals_fn)(globals_bytes, entity_id);

    (*env)->ReleaseByteArrayElements(env, globals, globals_bytes, 0);
}}

JNIEXPORT void JNICALL Java_{package_underscore}_{grug_class}_initGrugAdapter(JNIEnv *env, jobject obj) {{
    jni_version = (*env)->GetVersion(env);

    if ((*env)->GetJavaVM(env, &jvm) < 0) {{
        (*env)->ExceptionDescribe(env);
        exit(EXIT_FAILURE);
    }}

    grug_object = (*env)->NewGlobalRef(env, obj);
    CHECK_NEW_GLOBAL_REF(grug_object);

    jclass grug_class = (*env)->GetObjectClass(env, obj);

    runtime_error_handler_id = (*env)->GetMethodID(env, grug_class, "runtimeErrorHandler", "(Ljava/lang/String;ILjava/lang/String;Ljava/lang/String;)V");
    CHECK(env);

    game_functions_class = (*env)->FindClass(env, "Lcom/example/examplemod/GameFunctions;");
    CHECK(env);

"""

    for fn_index, (fn_name, fn) in enumerate(mod_api["game_functions"].items()):
        if fn_index > 0:
            output += "\n"

        output += f'    game_fn_{fn_name}_id = (*env)->GetStaticMethodID(env, game_functions_class, "{fn_name}", "('

        if "arguments" in fn:
            for argument in fn["arguments"]:
                output += get_signature_type(argument["type"])

        output += ")"

        output += get_signature_type(fn["return_type"]) if "return_type" in fn else "V"

        output += '");\n'

        output += f"    CHECK(env);\n"

    output += "}\n"

    output += f"""
JNIEXPORT void JNICALL Java_{package_underscore}_{grug_class}_fillRootGrugDir(JNIEnv *env, jobject obj, jobject dir_object) {{
    (void)obj;

    jclass dir_class = (*env)->GetObjectClass(env, dir_object);

    jfieldID name_fid = (*env)->GetFieldID(env, dir_class, "name", "Ljava/lang/String;");
    CHECK(env);
    jstring name = (*env)->NewStringUTF(env, grug_mods.name);
    CHECK(env);
    (*env)->SetObjectField(env, dir_object, name_fid, name);

    jfieldID dirs_size_fid = (*env)->GetFieldID(env, dir_class, "dirsSize", "I");
    CHECK(env);
    (*env)->SetIntField(env, dir_object, dirs_size_fid, (jint)grug_mods.dirs_size);

    jfieldID files_size_fid = (*env)->GetFieldID(env, dir_class, "filesSize", "I");
    CHECK(env);
    (*env)->SetIntField(env, dir_object, files_size_fid, (jint)grug_mods.files_size);

    jfieldID address_fid = (*env)->GetFieldID(env, dir_class, "address", "J");
    CHECK(env);
    (*env)->SetLongField(env, dir_object, address_fid, (jlong)&grug_mods);
}}

JNIEXPORT void JNICALL Java_{package_underscore}_{grug_class}_fillGrugDir(JNIEnv *env, jobject obj, jobject dir_object, jlong parent_dir_address, jint dir_index) {{
    (void)obj;

    jclass dir_class = (*env)->GetObjectClass(env, dir_object);

    struct grug_mod_dir *parent_dir = (struct grug_mod_dir *)parent_dir_address;

    struct grug_mod_dir dir = parent_dir->dirs[dir_index];

    jfieldID name_fid = (*env)->GetFieldID(env, dir_class, "name", "Ljava/lang/String;");
    CHECK(env);
    jstring name = (*env)->NewStringUTF(env, dir.name);
    CHECK(env);
    (*env)->SetObjectField(env, dir_object, name_fid, name);

    jfieldID dirs_size_fid = (*env)->GetFieldID(env, dir_class, "dirsSize", "I");
    CHECK(env);
    (*env)->SetIntField(env, dir_object, dirs_size_fid, (jint)dir.dirs_size);

    jfieldID files_size_fid = (*env)->GetFieldID(env, dir_class, "filesSize", "I");
    CHECK(env);
    (*env)->SetIntField(env, dir_object, files_size_fid, (jint)dir.files_size);

    jfieldID address_fid = (*env)->GetFieldID(env, dir_class, "address", "J");
    CHECK(env);
    (*env)->SetLongField(env, dir_object, address_fid, (jlong)&parent_dir->dirs[dir_index]);
}}

JNIEXPORT void JNICALL Java_{package_underscore}_{grug_class}_fillGrugFile(JNIEnv *env, jobject obj, jobject file_object, jlong parent_dir_address, jint file_index) {{
    (void)obj;

    jclass file_class = (*env)->GetObjectClass(env, file_object);

    struct grug_mod_dir *parent_dir = (struct grug_mod_dir *)parent_dir_address;

    struct grug_file file = parent_dir->files[file_index];

    jfieldID name_fid = (*env)->GetFieldID(env, file_class, "name", "Ljava/lang/String;");
    CHECK(env);
    jstring name = (*env)->NewStringUTF(env, file.name);
    CHECK(env);
    (*env)->SetObjectField(env, file_object, name_fid, name);

    jfieldID entity_fid = (*env)->GetFieldID(env, file_class, "entity", "Ljava/lang/String;");
    CHECK(env);
    jstring entity = (*env)->NewStringUTF(env, file.entity);
    CHECK(env);
    (*env)->SetObjectField(env, file_object, entity_fid, entity);

    jfieldID entity_type_fid = (*env)->GetFieldID(env, file_class, "entityType", "Ljava/lang/String;");
    CHECK(env);
    jstring entity_type = (*env)->NewStringUTF(env, file.entity_type);
    CHECK(env);
    (*env)->SetObjectField(env, file_object, entity_type_fid, entity_type);

    jfieldID dll_fid = (*env)->GetFieldID(env, file_class, "dll", "J");
    CHECK(env);
    (*env)->SetLongField(env, file_object, dll_fid, (jlong)file.dll);

    jfieldID globals_size_fid = (*env)->GetFieldID(env, file_class, "globalsSize", "I");
    CHECK(env);
    (*env)->SetIntField(env, file_object, globals_size_fid, (jint)file.globals_size);

    jfieldID init_globals_fn_fid = (*env)->GetFieldID(env, file_class, "initGlobalsFn", "J");
    CHECK(env);
    (*env)->SetLongField(env, file_object, init_globals_fn_fid, (jlong)file.init_globals_fn);

    jfieldID on_fns_fid = (*env)->GetFieldID(env, file_class, "onFns", "J");
    CHECK(env);
    (*env)->SetLongField(env, file_object, on_fns_fid, (jlong)file.on_fns);

    jfieldID resource_mtimes_fid = (*env)->GetFieldID(env, file_class, "resourceMtimes", "J");
    CHECK(env);
    (*env)->SetLongField(env, file_object, resource_mtimes_fid, (jlong)file.resource_mtimes);
}}

JNIEXPORT void JNICALL Java_{package_underscore}_{grug_class}_getEntityFile(JNIEnv *env, jobject obj, jstring java_entity, jobject file_object) {{
    (void)obj;

    jclass file_class = (*env)->GetObjectClass(env, file_object);

    const char *c_entity = (*env)->GetStringUTFChars(env, java_entity, NULL);
    CHECK(env);

    struct grug_file *file_ptr = grug_get_entity_file((char *)c_entity);
    assert(file_ptr);
    struct grug_file file = *file_ptr;

    (*env)->ReleaseStringUTFChars(env, java_entity, c_entity);

    jfieldID name_fid = (*env)->GetFieldID(env, file_class, "name", "Ljava/lang/String;");
    CHECK(env);
    jstring name = (*env)->NewStringUTF(env, file.name);
    CHECK(env);
    (*env)->SetObjectField(env, file_object, name_fid, name);

    jfieldID entity_fid = (*env)->GetFieldID(env, file_class, "entity", "Ljava/lang/String;");
    CHECK(env);
    jstring entity = (*env)->NewStringUTF(env, file.entity);
    CHECK(env);
    (*env)->SetObjectField(env, file_object, entity_fid, entity);

    jfieldID entity_type_fid = (*env)->GetFieldID(env, file_class, "entityType", "Ljava/lang/String;");
    CHECK(env);
    jstring entity_type = (*env)->NewStringUTF(env, file.entity_type);
    CHECK(env);
    (*env)->SetObjectField(env, file_object, entity_type_fid, entity_type);

    jfieldID dll_fid = (*env)->GetFieldID(env, file_class, "dll", "J");
    CHECK(env);
    (*env)->SetLongField(env, file_object, dll_fid, (jlong)file.dll);

    jfieldID globals_size_fid = (*env)->GetFieldID(env, file_class, "globalsSize", "I");
    CHECK(env);
    (*env)->SetIntField(env, file_object, globals_size_fid, (jint)file.globals_size);

    jfieldID init_globals_fn_fid = (*env)->GetFieldID(env, file_class, "initGlobalsFn", "J");
    CHECK(env);
    (*env)->SetLongField(env, file_object, init_globals_fn_fid, (jlong)file.init_globals_fn);

    jfieldID on_fns_fid = (*env)->GetFieldID(env, file_class, "onFns", "J");
    CHECK(env);
    (*env)->SetLongField(env, file_object, on_fns_fid, (jlong)file.on_fns);

    jfieldID resource_mtimes_fid = (*env)->GetFieldID(env, file_class, "resourceMtimes", "J");
    CHECK(env);
    (*env)->SetLongField(env, file_object, resource_mtimes_fid, (jlong)file.resource_mtimes);
}}

JNIEXPORT void JNICALL Java_{package_underscore}_{grug_class}_setOnFnsToSafeMode(JNIEnv *env, jobject obj) {{
    (void)env;
    (void)obj;

    grug_set_on_fns_to_safe_mode();
}}

JNIEXPORT void JNICALL Java_{package_underscore}_{grug_class}_setOnFnsToFastMode(JNIEnv *env, jobject obj) {{
    (void)env;
    (void)obj;

    grug_set_on_fns_to_fast_mode();
}}

JNIEXPORT jboolean JNICALL Java_{package_underscore}_{grug_class}_areOnFnsInSafeMode(JNIEnv *env, jobject obj) {{
    (void)env;
    (void)obj;

    return grug_are_on_fns_in_safe_mode();
}}

JNIEXPORT void JNICALL Java_{package_underscore}_{grug_class}_toggleOnFnsMode(JNIEnv *env, jobject obj) {{
    (void)env;
    (void)obj;

    grug_toggle_on_fns_mode();
}}
"""

    for entity_name, entity in mod_api["entities"].items():
        if "on_functions" not in entity:
            continue

        for on_fn_name, on_fn in entity["on_functions"].items():
            output += f"""
JNIEXPORT jboolean JNICALL Java_{package_underscore}_{grug_class}_{entity_name.replace("_", "_1")}_1has_1{on_fn_name.replace("_", "_1")}(JNIEnv *env, jobject obj, jlong on_fns) {{
    (void)env;
    (void)obj;

    return ((struct {entity_name}_on_fns *)on_fns)->{on_fn_name} != NULL;
}}

JNIEXPORT void JNICALL Java_{package_underscore}_{grug_class}_{entity_name.replace("_", "_1")}_1{on_fn_name.replace("_", "_1")}(JNIEnv *env, jclass clazz, jlong on_fns, jbyteArray globals) {{
    (void)clazz;

    jbyte *globals_bytes = (*env)->GetByteArrayElements(env, globals, NULL);
    CHECK(env);

    ((struct {entity_name}_on_fns *)on_fns)->{on_fn_name}(globals_bytes);

    (*env)->ReleaseByteArrayElements(env, globals, globals_bytes, 0);
}}
"""

    return output


# From the "Type Signatures" header here:
# https://docs.oracle.com/javase/8/docs/technotes/guides/jni/spec/types.html
def get_signature_type(typ):
    if typ == "i32":
        return "I"
    elif typ == "f32":
        return "F"
    elif typ == "id":
        return "J"
    elif typ == "string":
        return "Ljava/lang/String;"
    elif typ == "bool":
        return "Z"

    # TODO: Support more types
    assert False


def main(mod_api_path, output_path, package_slash, grug_class):
    with open(mod_api_path) as f:
        mod_api = json.load(f)

    with open(output_path, "w") as f:
        f.write(get_output(mod_api, package_slash, grug_class))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
