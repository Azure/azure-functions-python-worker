import os
import jupyter_client
from ipykernel.kernelspec import install as install_ipykernel
from jupyter_client.kernelspec import KernelSpecManager

class KernelHandler:
    def __init__(self, kernel_name="func-kernel"):
        self.kernel_name = kernel_name
        self._ensure_kernel_registered()
        self.km = jupyter_client.KernelManager(kernel_name=self.kernel_name)
        self.km.start_kernel()
        self.kc = self.km.client()
        self.kc.start_channels()
        self._wait_for_ready()

    def _ensure_kernel_registered(self):
        ksm = KernelSpecManager()
        try:
            ksm.get_kernel_spec(self.kernel_name)
        except jupyter_client.kernelspec.NoSuchKernel:
            print(f"Kernel '{self.kernel_name}' not found. Installing...")
            install_ipykernel(user=True, kernel_name=self.kernel_name, display_name="Function App Kernel")
            print(f"Kernel '{self.kernel_name}' installed.")

    def _wait_for_ready(self):
        self.kc.wait_for_ready(timeout=10)

    def run_code(self, code):
        msg_id = self.kc.execute(code)
        result = ""
        while True:
            msg = self.kc.get_iopub_msg(timeout=5)
            if msg['parent_header'].get('msg_id') != msg_id:
                continue
            msg_type = msg['msg_type']
            if msg_type == 'stream':
                result += msg['content']['text']
            elif msg_type == 'execute_result':
                result += msg['content']['data'].get('text/plain', '')
            elif msg_type == 'error':
                result += "\n".join(msg['content']['traceback'])
            elif msg_type == 'status' and msg['content']['execution_state'] == 'idle':
                break
        return result

    def shutdown(self):
        self.kc.stop_channels()
        self.km.shutdown_kernel()
