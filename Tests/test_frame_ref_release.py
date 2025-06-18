import weakref
import gc
import pobshell

class Sentinel:
    pass

def test_pobshell_shell_frame_release():
    ref_holder = {}

    def create_and_run_shell():
        sentinel = Sentinel()
        ref_holder['sentinel_weak'] = weakref.ref(sentinel)
        pobshell.shell()
        # Don't return anything; we want sentinel to die with this frame

    create_and_run_shell()
    gc.collect()

    if ref_holder['sentinel_weak']() is None:
        print("✅ No frame or local reference retained — shell test passed.")
    else:
        print("❌ Pobshell.shell retained the calling frame or its locals!")
        # Inspect why it's retained
        sentinel = ref_holder['sentinel_weak']()
        print("🔎 Checking who is still referencing sentinel...")
        for ref in gc.get_referrers(sentinel):
            print("🔗 Referrer:", type(ref))
            if isinstance(ref, dict):
                for k, v in ref.items():
                    if v is sentinel:
                        print(f" - via dict key: {k}")
            elif hasattr(ref, '__dict__'):
                for k, v in vars(ref).items():
                    if v is sentinel:
                        print(f" - via attr: {k}")

def test_pobshell_pob_frame_release():
    ref_holder = {}

    def create_and_run_shell():
        foo = 'foofoo'
        sentinel = Sentinel()
        ref_holder['sentinel_weak'] = weakref.ref(sentinel)
        POB = pobshell.pob()
        POB.onecmd_plus_hooks('ls -l')
        POB.onecmd_plus_hooks('ls -x foo')
        POB.exit()
        POB = pobshell.pob(foo)
        POB.onecmd_plus_hooks('ls -x .')
        POB.onecmd_plus_hooks('quit')
        # Don't return anything; we want sentinel to die with this frame

    create_and_run_shell()
    gc.collect()

    if ref_holder['sentinel_weak']() is None:
        print("✅ No frame or local reference retained — pob test passed.")
    else:
        print("❌ Pobshell.pob retained the calling frame or its locals!")
        # Inspect why it's retained
        sentinel = ref_holder['sentinel_weak']()
        print("🔎 Checking who is still referencing sentinel...")
        for ref in gc.get_referrers(sentinel):
            print("🔗 Referrer:", type(ref))
            if isinstance(ref, dict):
                for k, v in ref.items():
                    if v is sentinel:
                        print(f" - via dict key: {k}")
            elif hasattr(ref, '__dict__'):
                for k, v in vars(ref).items():
                    if v is sentinel:
                        print(f" - via attr: {k}")

test_pobshell_pob_frame_release()
test_pobshell_shell_frame_release()

