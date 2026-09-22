"""Real subprocess cancellation and error-disclosure regressions."""

import json
import os
import select
import signal
import subprocess
import sys
import textwrap
from contextlib import suppress
from pathlib import Path
from types import FrameType

import pytest

from .harness import ROOT, Stack, require_owned


@pytest.mark.parametrize("phase", ["ready", "acquiring"])
def test_sigterm_cleans_exact_owned_resources(phase: str) -> None:
    script = textwrap.dedent('''
        import json, signal, subprocess, sys, time
        from tests.system.harness import Stack
        def publish(stack):
            child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            stack.processes.append(child)
            print(json.dumps(dict(run=stack.run, identifier=stack.identifier,
                                  directory=str(stack.directory), pid=child.pid)), flush=True)
        class Probe(Stack):
            def command(self, args, **kwargs):
                result = super().command(args, **kwargs)
                if len(args) > 2 and args[2] == 'create' and sys.argv[1] == 'acquiring':
                    assert self.identifier is None
                    publish(self)
                    time.sleep(1)
                return result
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        try:
            with Probe() as stack:
                if sys.argv[1] == 'ready':
                    publish(stack)
                time.sleep(120)
        except SystemExit as error:
            assert error.code == 128 + signal.SIGTERM
        assert signal.getsignal(signal.SIGTERM) == signal.SIG_DFL
        print('previous-handler', flush=True)
        signal.raise_signal(signal.SIGTERM)
    ''')
    probe = subprocess.Popen([sys.executable, "-c", script, phase], cwd=ROOT,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    controller = Stack()
    state = None
    try:
        assert probe.stdout is not None
        assert select.select([probe.stdout], [], [], 60)[0], "probe readiness deadline"
        state = json.loads(probe.stdout.readline())
        name = f"threshold-system-{state['run']}"
        resource = json.loads(controller.pod("inspect", name))[0]
        identifier = resource["Id"]
        require_owned(resource, state["run"], identifier)
        probe.send_signal(signal.SIGTERM)
        stdout, stderr = probe.communicate(timeout=30)
        remaining = controller.pod("ps", "--all", "--filter", f"id={identifier}",
                                   "--format", "{{.ID}}")
        assert not remaining.strip(), "SIGTERM left the exact owned container"
        assert not Path(state["directory"]).exists(), "SIGTERM left private directory"
        assert not Path(f"/proc/{state['pid']}").exists(), "SIGTERM left owned child"
        assert probe.returncode == -signal.SIGTERM, "outside SIGTERM behavior changed"
        assert "previous-handler" in stdout, "original handler was not restored"
        assert not stderr
    finally:
        if probe.poll() is None:
            probe.kill()
            probe.wait(timeout=5)
        if state:
            # Recovery is exact-owner checked even when the regression is RED.
            resources = json.loads(controller.pod("ps", "--all", "--filter",
                                                  f"name=threshold-system-{state['run']}",
                                                  "--format", "json"))
            if resources:
                resource = json.loads(controller.pod(
                    "inspect", f"threshold-system-{state['run']}"))[0]
                require_owned(resource, state["run"], resource["Id"])
                controller.pod("rm", "--force", resource["Id"])
            with suppress(ProcessLookupError):
                os.kill(state["pid"], signal.SIGTERM)
            directory = Path(state["directory"])
            assert directory.name.startswith(f"threshold-system-{state['run']}-")
            if directory.exists():
                directory.rmdir()


def test_normal_exception_restores_sigterm_handler() -> None:
    def previous(signum: int, frame: FrameType | None) -> None:
        pass

    original = signal.signal(signal.SIGTERM, previous)
    stack = Stack()
    try:
        with pytest.raises(ValueError, match="ordinary failure"), stack:
            raise ValueError("ordinary failure")
        assert signal.getsignal(signal.SIGTERM) is previous
    finally:
        signal.signal(signal.SIGTERM, original)
    assert not stack.directory.exists()
    assert not stack.pod("ps", "--all", "--filter", f"id={stack.identifier}",
                         "--format", "{{.ID}}").strip()
