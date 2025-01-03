import json
import sys


def get_output(mod_api, package_slash, grug_class):
    package_underscore = package_slash.replace("/", "_")

    output = """#define _GNU_SOURCE // TODO: REMOVE!

#include <jni.h>

#include "grug/grug.h"

#include <assert.h>
// #include <execinfo.h> // TODO: REMOVE!
#include <pthread.h> // TODO: REMOVE!
#include <stdbool.h>
#include <stdio.h>

typedef char* string;
typedef int32_t i32;
typedef uint64_t id;

#ifdef DONT_CHECK_EXCEPTIONS
#define CHECK(env)
#else
#define CHECK(env) {\\
    if ((*env)->ExceptionCheck(env)) {\\
        fprintf(stderr, "Exception detected at %s:%d\\n", __FILE__, __LINE__);\\
        (*env)->ExceptionDescribe(env);\\
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
jint jni_version;
JavaVM* jvm;

// pthread_t on_fn_thread;

// TODO: Get rid of this!
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

        output += f""") {{
    JNIEnv *env;
    FILL_ENV(env);

"""

        for field_index, field in enumerate(entity["fields"]):
            field_name = field["name"]

            if field_index > 0:
                output += "\n"

            if field["type"] == "string":
                output += f"    jstring {field_name} = (*env)->NewStringUTF(env, c_{field_name});\n"
                output += f"    CHECK(env);\n"
                output += f"    (*env)->SetObjectField(env, {entity_name}_definition_obj, {entity_name}_definition_{field_name}_fid, {field_name});\n"
            elif field["type"] == "i32":
                output += f"    (*env)->SetIntField(env, {entity_name}_definition_obj, {entity_name}_definition_{field_name}_fid, c_{field_name});\n"
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

            output += f"{argument["type"]} "

            if argument["type"] == "string":
                output += "c_"
            elif argument["type"] == "i32" or argument["type"] == "id":
                output += "java_"
            else:
                # TODO: Support more types
                assert False

            output += f"{argument["name"]}"

        output += f""") {{
    JNIEnv *env;
    FILL_ENV(env);

"""

        for argument_index, argument in enumerate(fn["arguments"]):
            argument_name = argument["name"]

            if argument["type"] == "i32" or argument["type"] == "id":
                continue

            # TODO: Support more types
            assert argument["type"] == "string"

            if argument_index > 0:
                output += "\n"

            output += f"    jstring java_{argument_name} = (*env)->NewStringUTF(env, c_{argument_name});\n"
            output += f"    CHECK(env);\n"

        output += "    "

        if "return_type" in fn:
            if fn["return_type"] == "i32":
                output += "jint"
            elif fn["return_type"] == "id":
                output += "jlong"
            else:
                # TODO: Support more types
                assert False

            output += " result = "

        output += "(*env)->Call"

        if "return_type" not in fn:
            output += "Void"
        elif fn["return_type"] == "i32":
            output += "Int"
        elif fn["return_type"] == "id":
            output += "Long"
        else:
            # TODO: Support more types
            assert False

        output += f"Method(env, global_obj, game_fn_{fn_name}_id"

        for argument_index, argument in enumerate(fn["arguments"]):
            output += f", java_{argument["name"]}"

        output += ");\n"

        output += "    CHECK(env);\n"

        if "return_type" in fn:
            output += "    return result;\n"

        output += "}\n"

        output += "\n"

    output += f"""void runtime_error_handler(char *reason, enum grug_runtime_error_type type, char *on_fn_name, char *on_fn_path) {{
    // pthread_t thread = pthread_self();
    // fprintf(stderr, "runtime_error_handler() thread: %lu\\n", thread);

    // #define MAX_THREAD_NAME_LEN 420
    // static char thread_name[MAX_THREAD_NAME_LEN];
    // assert(pthread_getname_np(thread, thread_name, MAX_THREAD_NAME_LEN) == 0);
    // fprintf(stderr, "thread_name: '%s'\\n", thread_name);

    JNIEnv *env;

    jint result;

    // TODO: Replace with FILL_ENV(env)
    // This call sporadically returns -2 (JNI_EDETACHED: thread detached from the VM)
    result = (*jvm)->GetEnv(jvm, (void**)&env, jni_version);
    if (result != JNI_OK) {{
        fprintf(stderr, "GetEnv failed in runtime_error_handler() with result %d on line %d\\n", result, __LINE__);
        // exit(EXIT_FAILURE);
    }}

    // #define BT_BUF_SIZE 420

    // void *buffer[BT_BUF_SIZE];

    // int nptrs = backtrace(buffer, BT_BUF_SIZE);
    // printf("backtrace() returned %d addresses\\n", nptrs);

    // backtrace_symbols_fd(buffer, nptrs, STDERR_FILENO);

    // See https://stackoverflow.com/a/12900986/13279557
    JavaVMAttachArgs args;
    args.version = jni_version;
    args.name = NULL; // you might want to give the java thread a name
    args.group = NULL; // you might want to assign the java thread to a ThreadGroup

    // TODO: REMOVE
    // This call sporadically returns -1 (JNI_ERR: unknown error)
    result = (*jvm)->AttachCurrentThread(jvm, (void**)&env, &args);
    if (result < 0) {{
        fprintf(stderr, "AttachCurrentThread failed in runtime_error_handler() with result %d\\n", result);
        abort();
    }}

    jstring java_reason = (*env)->NewStringUTF(env, reason);
    CHECK(env);
    jint java_type = type;
    jstring java_on_fn_name = (*env)->NewStringUTF(env, on_fn_name);
    CHECK(env);
    jstring java_on_fn_path = (*env)->NewStringUTF(env, on_fn_path);
    CHECK(env);

    (*env)->CallVoidMethod(env, global_obj, runtime_error_handler_id, java_reason, java_type, java_on_fn_name, java_on_fn_path);
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

JNIEXPORT jstring JNICALL Java_{package_underscore}_{grug_class}_onFnName(JNIEnv *env, jobject obj) {{
    (void)obj;

    return (*env)->NewStringUTF(env, grug_on_fn_name);
}}

JNIEXPORT jstring JNICALL Java_{package_underscore}_{grug_class}_onFnPath(JNIEnv *env, jobject obj) {{
    (void)obj;

    return (*env)->NewStringUTF(env, grug_on_fn_path);
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

    jfieldID dll_fid = (*env)->GetFieldID(env, file_class, "dll", "J");
    CHECK(env);
    (*env)->SetLongField(env, file_object, dll_fid, (jlong)c_file.dll);

    jfieldID define_fn_fid = (*env)->GetFieldID(env, file_class, "defineFn", "J");
    CHECK(env);
    (*env)->SetLongField(env, file_object, define_fn_fid, (jlong)c_file.define_fn);

    jfieldID globals_size_fid = (*env)->GetFieldID(env, file_class, "globalsSize", "I");
    CHECK(env);
    (*env)->SetIntField(env, file_object, globals_size_fid, (jint)c_file.globals_size);

    jfieldID init_globals_fn_fid = (*env)->GetFieldID(env, file_class, "initGlobalsFn", "J");
    CHECK(env);
    (*env)->SetLongField(env, file_object, init_globals_fn_fid, (jlong)c_file.init_globals_fn);

    jfieldID define_type_fid = (*env)->GetFieldID(env, file_class, "defineType", "Ljava/lang/String;");
    CHECK(env);
    jstring define_type = (*env)->NewStringUTF(env, c_file.define_type);
    CHECK(env);
    (*env)->SetObjectField(env, file_object, define_type_fid, define_type);

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

    pid_t tid = gettid();
    fprintf(stderr, "initGrugAdapter() tid: %d\\n", tid);

    pthread_t thread = pthread_self();

    // TODO: REMOVE
    #define MAX_THREAD_NAME_LEN 420
    static char thread_name[MAX_THREAD_NAME_LEN];
    assert(pthread_getname_np(thread, thread_name, MAX_THREAD_NAME_LEN) == 0);
    fprintf(stderr, "thread_name: '%s'\\n", thread_name);

    global_obj = obj;

    jclass javaClass = (*env)->GetObjectClass(env, obj);

    runtime_error_handler_id = (*env)->GetMethodID(env, javaClass, "runtimeErrorHandler", "(Ljava/lang/String;ILjava/lang/String;Ljava/lang/String;)V");
    CHECK(env);

    jclass entity_definitions_class = (*env)->FindClass(env, "{package_slash}/EntityDefinitions");
    CHECK(env);
"""

    output += "\n"

    for entity_name, entity in mod_api["entities"].items():
        output += f'    jfieldID {entity_name}_definition_fid = (*env)->GetStaticFieldID(env, entity_definitions_class, "{snake_to_camel(entity_name)}", "L{package_slash}/Grug{snake_to_pascal(entity_name)};");\n'
        output += f"    CHECK(env);\n"

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

            output += (
                f"    CHECK(env);\n"
            )

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

    jfieldID dll_fid = (*env)->GetFieldID(env, file_class, "dll", "J");
    CHECK(env);
    (*env)->SetLongField(env, file_object, dll_fid, (jlong)file.dll);

    jfieldID define_fn_fid = (*env)->GetFieldID(env, file_class, "defineFn", "J");
    CHECK(env);
    (*env)->SetLongField(env, file_object, define_fn_fid, (jlong)file.define_fn);

    jfieldID globals_size_fid = (*env)->GetFieldID(env, file_class, "globalsSize", "I");
    CHECK(env);
    (*env)->SetIntField(env, file_object, globals_size_fid, (jint)file.globals_size);

    jfieldID init_globals_fn_fid = (*env)->GetFieldID(env, file_class, "initGlobalsFn", "J");
    CHECK(env);
    (*env)->SetLongField(env, file_object, init_globals_fn_fid, (jlong)file.init_globals_fn);

    jfieldID define_type_fid = (*env)->GetFieldID(env, file_class, "defineType", "Ljava/lang/String;");
    CHECK(env);
    jstring define_type = (*env)->NewStringUTF(env, file.define_type);
    CHECK(env);
    (*env)->SetObjectField(env, file_object, define_type_fid, define_type);

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

    jfieldID dll_fid = (*env)->GetFieldID(env, file_class, "dll", "J");
    CHECK(env);
    (*env)->SetLongField(env, file_object, dll_fid, (jlong)file.dll);

    jfieldID define_fn_fid = (*env)->GetFieldID(env, file_class, "defineFn", "J");
    CHECK(env);
    (*env)->SetLongField(env, file_object, define_fn_fid, (jlong)file.define_fn);

    jfieldID globals_size_fid = (*env)->GetFieldID(env, file_class, "globalsSize", "I");
    CHECK(env);
    (*env)->SetIntField(env, file_object, globals_size_fid, (jint)file.globals_size);

    jfieldID init_globals_fn_fid = (*env)->GetFieldID(env, file_class, "initGlobalsFn", "J");
    CHECK(env);
    (*env)->SetLongField(env, file_object, init_globals_fn_fid, (jlong)file.init_globals_fn);

    jfieldID define_type_fid = (*env)->GetFieldID(env, file_class, "defineType", "Ljava/lang/String;");
    CHECK(env);
    jstring define_type = (*env)->NewStringUTF(env, file.define_type);
    CHECK(env);
    (*env)->SetObjectField(env, file_object, define_type_fid, define_type);

    jfieldID on_fns_fid = (*env)->GetFieldID(env, file_class, "onFns", "J");
    CHECK(env);
    (*env)->SetLongField(env, file_object, on_fns_fid, (jlong)file.on_fns);

    jfieldID resource_mtimes_fid = (*env)->GetFieldID(env, file_class, "resourceMtimes", "J");
    CHECK(env);
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
            output += f"JNIEXPORT jboolean JNICALL Java_{package_underscore}_{grug_class}_{snake_to_camel(entity_name)}_1has_1{snake_to_camel(on_fn_name)}(JNIEnv *env, jobject obj, jlong on_fns) {{\n"

            output += f"""    (void)env;
    (void)obj;

    return ((struct {entity_name}_on_fns *)on_fns)->{on_fn_name} != NULL;
"""

            output += "}\n"

            output += "\n"

            output += f"JNIEXPORT void JNICALL Java_{package_underscore}_{grug_class}_{snake_to_camel(entity_name)}_1{snake_to_camel(on_fn_name)}(JNIEnv *env, jobject obj, jlong on_fns, jbyteArray globals) {{\n"

            output += f"""    global_obj = obj;

    // on_fn_thread = pthread_self();
    // fprintf(stderr, "Java_game_Game_tool_1onUse() thread: %lu\\n", on_fn_thread);

    // pthread_t thread = pthread_self();

    // TODO: REMOVE
    // #define MAX_THREAD_NAME_LEN 420
    // static char thread_name[MAX_THREAD_NAME_LEN];
    // assert(pthread_getname_np(thread, thread_name, MAX_THREAD_NAME_LEN) == 0);
    // fprintf(stderr, "thread_name: '%s'\\n", thread_name);

    jbyte *globals_bytes = (*env)->GetByteArrayElements(env, globals, NULL);
    CHECK(env);

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
    if typ == "i32":
        return "I"
    elif typ == "id":
        return "J"
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
