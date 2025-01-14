import json
import os
from dataclasses import dataclass, field
from typing import Tuple, Dict, List, TypedDict, Optional, Literal, Any

import yaml
from deepdiff import DeepDiff

from acto.common import postprocess_diff, EXCLUDE_PATH_REGEX, Diff


class PodLog(TypedDict):
    log: Optional[List[str]]
    previous_log: Optional[List[str]]


@dataclass
class Snapshot:
    input: dict = field(default_factory=dict)
    cli_result: dict = field(default_factory=dict)
    system_state: dict = field(default_factory=dict)
    operator_log: List[str] = field(default_factory=list)
    events: dict = field(default_factory=dict)
    not_ready_pods_logs: dict = field(default_factory=dict)
    coverage_files: Dict[str, bytes] = field(default_factory=dict)
    generation: int = 0
    trial_state: Literal['normal', 'recovering', 'terminated', 'runtime_exception'] = 'normal'
    parent: Optional['Snapshot'] = None
    __context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            'input': self.input,
            'cli_result': self.cli_result,
            'system_state': self.system_state,
            'operator_log': self.operator_log
        }

    def delta(self, prev: 'Snapshot') -> Tuple[Dict[str, Dict[str, Dict[str, Diff]]], Dict[str, Dict[str, Dict[str, Diff]]]]:
        curr_input, curr_system_state = self.input, self.system_state
        prev_input, prev_system_state = prev.input, prev.system_state

        input_delta = postprocess_diff(DeepDiff(prev_input, curr_input, view='tree'))

        system_state_delta = {}
        for resource in curr_system_state:
            if resource not in prev_system_state:
                prev_system_state[resource] = {}
            system_state_delta[resource] = postprocess_diff(
                DeepDiff(prev_system_state[resource],
                         curr_system_state[resource],
                         exclude_regex_paths=EXCLUDE_PATH_REGEX,
                         view='tree'))

        return input_delta, system_state_delta

    def save(self, base_dir: str):
        yaml.safe_dump(self.input, open(os.path.join(base_dir, f'mutated-{self.generation}.yaml'), 'w'))
        json.dump(self.cli_result, open(os.path.join(base_dir, f'cli-output-{self.generation}.log'), 'w'))
        json.dump(self.system_state, open(os.path.join(base_dir, f'system-state-{self.generation}.json'), 'w'), default=str)
        open(os.path.join(base_dir, f'operator-{self.generation}.json'), 'w').write('\n'.join(self.operator_log))
        json.dump(self.events, open(os.path.join(base_dir, f'events-{self.generation}.json'), 'w'))
        json.dump(self.not_ready_pods_logs, open(os.path.join(base_dir, f'not-ready-pods-logs-{self.generation}.json'), 'w'))
        open(os.path.join(base_dir, f'trial-state-{self.generation}.txt'), 'w').write(self.trial_state)
        # dump coverage info
        # converge_index is a dict to map from filename to its generation
        coverage_index_path = os.path.join(base_dir, f'coverage-index.json')
        if not os.path.exists(coverage_index_path):
            open(coverage_index_path, 'w').write('{}')
            coverage_index = {}
        else:
            coverage_index = json.load(open(coverage_index_path))

        for filename, content in self.coverage_files.items():
            if filename not in coverage_index:
                with open(os.path.join(base_dir, filename), 'wb') as f:
                    f.write(content)
                coverage_index[filename] = self.generation
        json.dump(coverage_index, open(coverage_index_path, 'w'))

    def get_context_value(self, key: str):
        if key in self.__context:
            return self.__context[key]
        if self.parent:
            return self.parent.get_context_value(key)
        return None

    def set_context_value(self, key: str, value: Any):
        self.__context[key] = value
