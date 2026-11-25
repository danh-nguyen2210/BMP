"""Job-wide Windows commit limit for the lifetime of a SAT runner process."""

import ctypes as ct
from ctypes import wintypes as wt
from contextlib import ExitStack


class BasicLimits(ct.Structure):
    _fields_ = [('process_time', ct.c_longlong), ('job_time', ct.c_longlong),
                ('flags', wt.DWORD), ('min_ws', ct.c_size_t), ('max_ws', ct.c_size_t),
                ('active_processes', wt.DWORD), ('affinity', ct.c_size_t),
                ('priority', wt.DWORD), ('scheduling', wt.DWORD)]


class ExtendedLimits(ct.Structure):
    _fields_ = [('basic', BasicLimits), ('io_counters', ct.c_ulonglong * 6),
                ('process_memory', ct.c_size_t), ('job_memory', ct.c_size_t),
                ('peak_process_memory', ct.c_size_t), ('peak_job_memory', ct.c_size_t)]


class CompletionPort(ct.Structure):
    _fields_ = [('key', ct.c_void_p), ('handle', wt.HANDLE)]


class WindowsMemoryJob:
    """Set before spawning workers. Membership lasts until the runner exits."""

    def __init__(self, gib):
        self.gib = gib
        self._handles = ExitStack()
        kernel = ct.WinDLL('kernel32', use_last_error=True)

        def api(name, result, *args):
            func = getattr(kernel, name)
            func.argtypes = args
            func.restype = result
            return func

        def checked(result):
            if not result:
                raise ct.WinError(ct.get_last_error())
            return result

        H, D, P = wt.HANDLE, wt.DWORD, ct.c_void_p
        create_job = api('CreateJobObjectW', H, P, wt.LPCWSTR)
        create_port = api('CreateIoCompletionPort', H, H, H, ct.c_size_t, D)
        close = api('CloseHandle', wt.BOOL, H)
        set_info = api('SetInformationJobObject', wt.BOOL, H, ct.c_int, P, D)
        assign = api('AssignProcessToJobObject', wt.BOOL, H, H)
        self._dequeue = api('GetQueuedCompletionStatus', wt.BOOL, H, ct.POINTER(D),
                            ct.POINTER(ct.c_size_t), ct.POINTER(P), D)
        with ExitStack() as handles:
            job = checked(create_job(None, None))
            handles.callback(close, job)
            self._port = checked(create_port(H(-1), None, 0, 1))
            handles.callback(close, self._port)
            port = CompletionPort(1, self._port)
            checked(set_info(job, 7, ct.byref(port), ct.sizeof(port)))
            limits = ExtendedLimits()
            limits.basic.flags = 0x200  # JOB_OBJECT_LIMIT_JOB_MEMORY
            limits.job_memory = int(gib * 2**30)
            checked(set_info(job, 9, ct.byref(limits), ct.sizeof(limits)))
            checked(assign(job, H(-1)))  # GetCurrentProcess pseudo-handle
            self._handles = handles.pop_all()

    def limit_hit(self):
        """Consume OS notifications, including short-lived native worker failures."""
        message, key, process = wt.DWORD(), ct.c_size_t(), ct.c_void_p()
        hit = False
        while self._dequeue(self._port, ct.byref(message), ct.byref(key),
                            ct.byref(process), 0):
            hit |= message.value == 10  # JOB_OBJECT_MSG_JOB_MEMORY_LIMIT
        if ct.get_last_error() != 258:  # WAIT_TIMEOUT: queue is empty
            raise ct.WinError(ct.get_last_error())
        return hit

    def close(self):
        self._handles.close()
