import json
import sys


def get_output(mod_api, package_slash, grug_class):
    package_underscore = package_slash.replace("/", "_")

    output = """// THIS FILE WAS GENERATED BY grug-adapter-for-java, SO DON'T EDIT IT!

#define _GNU_SOURCE // TODO: REMOVE!

#include <jni.h>

#include "grug/grug.h"

#include <assert.h>
// #include <execinfo.h> // TODO: REMOVE!
#include <pthread.h> // TODO: REMOVE!
#include <stdbool.h>
#include <stdio.h>
#include <sys/mman.h>

typedef char* string;
typedef int32_t i32;
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

// TODO: Remove
// pthread_t on_fn_thread;

not_static jclass grug_class;

// This is used to temporarily switch to an mmap()ed stack.
// This is necessary, since the JVM turns page guards off for its threads.
// This means any stack overflows our C code causes can corrupt the JVM:
// https://hg.openjdk.org/jdk/jdk/file/8ae33203d600/src/hotspot/os/linux/os_linux.cpp#l3168
//
// I explain the solution this code takes in detail here: https://stackoverflow.com/a/79347305/13279557
static void *stack;
not_static int64_t real_rbp;
not_static int64_t real_rsp;
static jbyte *static_globals_bytes; // TODO: Move this inside of the on fn
static jlong static_on_fns; // TODO: Move this inside of the on fn

not_static jmethodID runtime_error_handler_id;
"""

    output += "\n"

    for name, entity in mod_api["entities"].items():
        output += f"// TODO: Either mark this static or non_static:\n"
        output += f"jobject {name}_definition_obj;\n"

        for field in entity["fields"]:
            output += f"// TODO: Either mark this static or non_static:\n"
            output += f"jfieldID {name}_definition_{field["name"]}_fid;\n"

        output += "\n"

    for name in mod_api["game_functions"].keys():
        output += f"not_static jmethodID game_fn_{name}_id;\n"

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

            if argument["type"] == "string" or argument["type"] == "i32" or argument["type"] == "id":
                output += "c_"
            else:
                # TODO: Support more types
                assert False

            output += f"{argument["name"]}"

        output += f""") {{
    static JNIEnv *env;
    FILL_ENV(env);

"""

        for argument_index, argument in enumerate(fn["arguments"]):
            argument_name = argument["name"]

            if argument_index > 0:
                output += "\n"

            if argument["type"] == "string":
                output += f"    static jstring java_{argument_name};\n"
                output += f"    java_{argument_name} = (*env)->NewStringUTF(env, c_{argument_name});\n"
                output += f"    CHECK(env);\n"
            elif argument["type"] == "i32":
                output += f"    static jint static_{argument_name};\n"
                output += f"    static_{argument_name} = c_{argument_name};\n"
            elif argument["type"] == "id":
                output += f"    static jlong static_{argument_name};\n"
                output += f"    static_{argument_name} = c_{argument_name};\n"
            else:
                # TODO: Support more types
                assert False

        output += f"""
    // write(STDERR_FILENO, "a\\n", 2);

    // Save fake_rbp and fake_rsp
    // Marking these static is necessary for restoring
    static int64_t fake_rsp;
    static int64_t fake_rbp;
    // __asm__ volatile("mov %%rsp, %0\\n\\t" : "=r" (fake_rsp));
    // write(STDERR_FILENO, "bb\\n", 3);
    // __asm__ volatile("mov %%rbp, %0\\n\\t" : "=r" (fake_rbp));
    // write(STDERR_FILENO, "ccc\\n", 4);

    // Assert 16-byte alignment
    assert((fake_rsp & 0xf) == 0);
    assert((fake_rbp & 0xf) == 0);

    // fprintf(stderr, "real_rbp: %p\\n", (void *)real_rbp);
    // fprintf(stderr, "real_rsp: %p\\n", (void *)real_rsp);

    // Use real_rbp and real_rsp
    // __asm__ volatile("mov %0, %%rsp\\n\\t" : : "r" (real_rsp));
    // write(STDERR_FILENO, "dddd\\n", 5);
    // __asm__ volatile("mov %0, %%rbp\\n\\t" : : "r" (real_rbp));
    // write(STDERR_FILENO, "eeeee\\n", 6);

    // Assert 16-byte alignment
    assert((real_rsp & 0xf) == 0);
    assert((real_rbp & 0xf) == 0);
"""

#         if fn_name == "print_i32":
#             output += """
#     fprintf(stderr, "env: %p\\n", (void *)env);
#     fprintf(stderr, "grug_class: %p\\n", (void *)grug_class);
#     fprintf(stderr, "game_fn_print_i32_id: %p\\n", (void *)game_fn_print_i32_id);
#     fprintf(stderr, "static_n: %d\\n", static_n);
#     write(STDERR_FILENO, "ffffff\\n", 7);
# """

        output += "\n"
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

        output += "(*env)->CallStatic"

        if "return_type" not in fn:
            output += "Void"
        elif fn["return_type"] == "i32":
            output += "Int"
        elif fn["return_type"] == "id":
            output += "Long"
        else:
            # TODO: Support more types
            assert False

        output += f"Method(env, grug_class, game_fn_{fn_name}_id"

        for argument_index, argument in enumerate(fn["arguments"]):
            output += ", "

            if argument["type"] == "string":
                output += "java_"
            elif argument["type"] == "i32" or argument["type"] == "id":
                output += "static_"
            else:
                # TODO: Support more types
                assert False

            output += argument["name"]

        output += ");\n"

        output += "    // write(STDERR_FILENO, \"ggggggg\\n\", 8);\n"
        output += "    CHECK(env);\n"

        output += """
    // Restore fake_rbp and fake_rsp
    // __asm__ volatile("mov %0, %%rsp\\n\\t" : : "r" (fake_rsp));
    // __asm__ volatile("mov %0, %%rbp\\n\\t" : : "r" (fake_rbp));
"""

        if "return_type" in fn:
            output += "\n"
            output += "    return result;\n"

        output += "}\n"

        output += "\n"

    output += f"""void runtime_error_handler(char *reason, enum grug_runtime_error_type type, char *on_fn_name, char *on_fn_path) {{
    write(STDERR_FILENO, "a\\n", 2);

    static JNIEnv *env;
    FILL_ENV(env);

    write(STDERR_FILENO, "bb\\n", 3);

    static jstring static_reason;
    static_reason = (*env)->NewStringUTF(env, reason);
    CHECK(env);

    write(STDERR_FILENO, "ccc\\n", 4);

    static jint static_type;
    static_type = type;

    write(STDERR_FILENO, "dddd\\n", 5);

    static jstring static_on_fn_name;
    static_on_fn_name = (*env)->NewStringUTF(env, on_fn_name);
    CHECK(env);

    write(STDERR_FILENO, "eeeee\\n", 6);

    static jstring static_on_fn_path;
    static_on_fn_path = (*env)->NewStringUTF(env, on_fn_path);
    CHECK(env);

    write(STDERR_FILENO, "ffffff\\n", 7);

    // Save fake_rbp and fake_rsp
    // Marking these static is necessary for restoring
    static int64_t fake_rsp;
    static int64_t fake_rbp;
    // __asm__ volatile("mov %%rsp, %0\\n\\t" : "=r" (fake_rsp));
    // __asm__ volatile("mov %%rbp, %0\\n\\t" : "=r" (fake_rbp));

    // Assert 16-byte alignment
    assert((fake_rsp & 0xf) == 0);
    assert((fake_rbp & 0xf) == 0);

    write(STDERR_FILENO, "ggggggg\\n", 8);

    fprintf(stderr, "reason: %s\\n", reason);
    fprintf(stderr, "on_fn_name: %s\\n", on_fn_name);
    fprintf(stderr, "on_fn_path: %s\\n", on_fn_path);

    // Use real_rbp and real_rsp
    // __asm__ volatile("mov %0, %%rsp\\n\\t" : : "r" (real_rsp));
    // __asm__ volatile("mov %0, %%rbp\\n\\t" : : "r" (real_rbp));

    // Assert 16-byte alignment
    assert((real_rsp & 0xf) == 0);
    assert((real_rbp & 0xf) == 0);

    write(STDERR_FILENO, "hhhhhhhh\\n", 9);

    // TODO: REMOVE!
    fprintf(stderr, "env: %p\\n", (void *)env);
    fprintf(stderr, "grug_class: %p\\n", (void *)grug_class);
    fprintf(stderr, "runtime_error_handler_id: %p\\n", (void *)runtime_error_handler_id);
    fprintf(stderr, "static_reason: %p\\n", (void *)static_reason);
    fprintf(stderr, "static_type: %d\\n", static_type);
    fprintf(stderr, "static_on_fn_name: %p\\n", (void *)static_on_fn_name);
    fprintf(stderr, "static_on_fn_path: %p\\n", (void *)static_on_fn_path);

    (*env)->CallStaticVoidMethod(env, grug_class, runtime_error_handler_id, static_reason, static_type, static_on_fn_name, static_on_fn_path);
    write(STDERR_FILENO, "iiiiiiiii\\n", 10);
    CHECK(env);

    write(STDERR_FILENO, "jjjjjjjjjj\\n", 11);

    // Restore fake_rbp and fake_rsp
    // __asm__ volatile("mov %0, %%rsp\\n\\t" : : "r" (fake_rsp));
    // __asm__ volatile("mov %0, %%rbp\\n\\t" : : "r" (fake_rbp));

    write(STDERR_FILENO, "kkkkkkkkkkk\\n", 12);
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

    grug_class = (*env)->NewGlobalRef(env, (*env)->GetObjectClass(env, obj));
    CHECK_NEW_GLOBAL_REF(grug_class);

    runtime_error_handler_id = (*env)->GetStaticMethodID(env, grug_class, "runtimeErrorHandler", "(Ljava/lang/String;ILjava/lang/String;Ljava/lang/String;)V");
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
        output += f"    CHECK_NEW_GLOBAL_REF({entity_name}_definition_obj);\n"

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

        output += f'    game_fn_{fn_name}_id = (*env)->GetStaticMethodID(env, grug_class, "gameFn_{snake_to_camel(fn_name)}", "('

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

    # TODO: Remove!
    output += """
extern jmp_buf grug_runtime_error_jmp_buffer;
extern grug_runtime_error_handler_t grug_runtime_error_handler;
void grug_disable_on_fn_runtime_error_handling(void);
void grug_enable_on_fn_runtime_error_handling(void);
char *grug_get_runtime_error_reason(void);
extern volatile sig_atomic_t grug_runtime_error_type;
extern sigset_t grug_block_mask;
static void dummy(void) {
    grug_on_fn_path = "tests/err_runtime/division_by_0/input.grug";
    grug_on_fn_name = "on_a";

    if (sigsetjmp(grug_runtime_error_jmp_buffer, 1)) {
        grug_runtime_error_handler(grug_get_runtime_error_reason(), grug_runtime_error_type, "on_a", "tests/err_runtime/division_by_0/input.grug");
        return;
    }

    grug_enable_on_fn_runtime_error_handling();

    // Only blocks SIGALRM
    pthread_sigmask(SIG_BLOCK, &grug_block_mask, 0);
    game_fn_print_i32(7);
    pthread_sigmask(SIG_UNBLOCK, &grug_block_mask, 0);

    grug_disable_on_fn_runtime_error_handling();

    return;
}
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

            output += f"JNIEXPORT void JNICALL Java_{package_underscore}_{grug_class}_{snake_to_camel(entity_name)}_1{snake_to_camel(on_fn_name)}(JNIEnv *env, jclass clazz, jlong on_fns, jbyteArray globals) {{\n"

            output += f"""    (void)clazz;

    fprintf(stderr, "In {snake_to_camel(on_fn_name)}\\n");

    // #define BT_BUF_SIZE 420
    // void *buffer[BT_BUF_SIZE];
    // int nptrs = backtrace(buffer, BT_BUF_SIZE);
    // fprintf(stderr, "backtrace() returned %d addresses\\n", nptrs);
    // backtrace_symbols_fd(buffer, nptrs, STDERR_FILENO);

    // on_fn_thread = pthread_self();
    // fprintf(stderr, "Java_game_Game_tool_1onUse() thread: %lu\\n", on_fn_thread);

    // pthread_t thread = pthread_self();

    // TODO: REMOVE
    // #define MAX_THREAD_NAME_LEN 420
    // static char thread_name[MAX_THREAD_NAME_LEN];
    // assert(pthread_getname_np(thread, thread_name, MAX_THREAD_NAME_LEN) == 0);
    // fprintf(stderr, "thread_name: '%s'\\n", thread_name);

    static_globals_bytes = (*env)->GetByteArrayElements(env, globals, NULL);
    CHECK(env);
    
    static_on_fns = on_fns;

    size_t page_count = 8192;
    size_t page_size = sysconf(_SC_PAGE_SIZE);
    size_t length = page_count * page_size;

    // TODO: Try getting rid of the MAP_GROWSDOWN, since its feature of growing the stack is unnecessary
    // TODO: I think the `static` can be removed from this
    static void *map;
    // map = mmap(NULL, length, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    map = mmap(NULL, length, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_GROWSDOWN, -1, 0);
    if (map == MAP_FAILED) {{
        perror("mmap");
        exit(EXIT_FAILURE);
    }}

    // Asserting 16-byte alignment here is not necessary,
    // since mmap() guarantees it with the args we pass it
    assert(((size_t)map & 0xf) == 0);

    stack = (char *)map + length;

    // Asserting 16-byte alignment here is not necessary,
    // since mmap() guarantees it with the args we pass it
    assert(((size_t)stack & 0xf) == 0);

    // Save rbp and rsp
    // __asm__ volatile("mov %%rsp, %0\\n\\t" : "=r" (real_rsp));
    // __asm__ volatile("mov %%rbp, %0\\n\\t" : "=r" (real_rbp));

    // Assert 16-byte alignment
    assert((real_rsp & 0xf) == 0);
    assert((real_rbp & 0xf) == 0);

    fprintf(stderr, "Preparing to call {on_fn_name}()\\n");

    // Set rbp and rsp to the very start of the mmap-ed memory
    //
    // TODO: I think setting rsp and rbp here is UB?:
    // "Another restriction is that the clobber list should not contain
    // the stack pointer register. This is because the compiler requires
    // the value of the stack pointer to be the same after an asm statement
    // as it was on entry to the statement. However, previous versions
    // of GCC did not enforce this rule and allowed the stack pointer
    // to appear in the list, with unclear semantics. This behavior
    // is deprecated and listing the stack pointer may become an error
    // in future versions of GCC."
    // From https://gcc.gnu.org/onlinedocs/gcc/Extended-Asm.html
    // __asm__ volatile("mov %0, %%rsp\\n\\t" : : "r" (stack));
    // __asm__ volatile("mov %0, %%rbp\\n\\t" : : "r" (stack));

    write(STDERR_FILENO, "Calling\\n", 8);
    fprintf(stderr, "stack: %p\\n", (void *)stack);
    fprintf(stderr, "static_on_fns: %p\\n", (void *)static_on_fns);
    fprintf(stderr, "static_globals_bytes: %p\\n", (void *)static_globals_bytes);

    // TODO: Put this back!
    // ((struct {entity_name}_on_fns *)static_on_fns)->{on_fn_name}(static_globals_bytes);

    // TODO: Remove this!
    while (true) {{
        dummy();
    }}

    // Restore rbp and rsp
    // __asm__ volatile("mov %0, %%rsp\\n\\t" : : "r" (real_rsp));
    // __asm__ volatile("mov %0, %%rbp\\n\\t" : : "r" (real_rbp));

    if (munmap(map, length) == -1) {{
        perror("munmap");
        exit(EXIT_FAILURE);
    }}

    (*env)->ReleaseByteArrayElements(env, globals, static_globals_bytes, 0);
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
