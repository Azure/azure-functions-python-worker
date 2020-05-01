from typing import List
import traceback


def extend_exception_message(exc: Exception, msg: str) -> Exception:
    # Reconstruct exception message
    # From: ImportModule: no module name
    #   To: ImportModule: no module name. msg
    old_tb = exc.__traceback__
    old_msg = getattr(exc, 'msg', None) or str(exc) or ''
    new_msg = (old_msg.rstrip('.') + '. ' + msg).rstrip()
    new_excpt = type(exc)(new_msg).with_traceback(old_tb)
    return new_excpt


def marshall_exception_trace(exc: Exception) -> str:
    stack_summary: traceback.StackSummary = traceback.extract_tb(
        exc.__traceback__)
    if isinstance(exc, ModuleNotFoundError):
        stack_summary = _marshall_module_not_found_error(stack_summary)
    return ''.join(stack_summary.format())


def _marshall_module_not_found_error(
    tbss: traceback.StackSummary
) -> traceback.StackSummary:
    tbss = _remove_frame_from_stack(tbss, '<frozen importlib._bootstrap>')
    tbss = _remove_frame_from_stack(
        tbss, '<frozen importlib._bootstrap_external>')
    return tbss


def _remove_frame_from_stack(
    tbss: traceback.StackSummary,
    framename: str
) -> traceback.StackSummary:
    filtered_stack_list: List[traceback.FrameSummary] = list(
        filter(lambda frame: getattr(frame, 'filename') != framename, tbss))
    filtered_stack: traceback.StackSummary = traceback.StackSummary.from_list(
        filtered_stack_list)
    return filtered_stack
