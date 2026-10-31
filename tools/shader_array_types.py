"""Backend-neutral registration of fixed local array shapes."""
import re
from shader_ast import ModelError

class FixedArrayTypes:
    def register(self, key, shape, fields):
        if key not in self.aggregates:
            if len(self.aggregates) >= 256:
                raise ModelError("More than 256 matrix/array types")
            self.aggregates[key] = shape
            self.records[key] = {"node": None, "fields": [
                {"name": name, "type": kind, "semantic": None, "id": None} for name, kind in fields]}
            if self.ready_shapes:
                self.check_shape(key, [])
        return key

    def array_type(self, name):
        base, _, suffix = name.partition("[")
        suffix = "[" + suffix
        if not re.fullmatch(r"(?:\[\s*[0-9]+\s*\])+", suffix):
            raise ModelError("Only fixed array lengths are supported")
        dimensions = [int(n) for n in re.findall(r"\[\s*([0-9]+)\s*\]", suffix)]
        if len(dimensions) > 16 or any(not 1 <= n <= 64 for n in dimensions):
            raise ModelError("Array length/depth exceeds the supported budget")
        result = self.named_type(base.strip())
        if result in ("void", "Texture2D", "SamplerState"):
            raise ModelError("Array element is not an ordinary value")
        for length in reversed(dimensions):
            key = f"$array{length}<{result}>"
            result = self.register(key, {"kind": "array", "length": length, "element": result},
                           [(f"e{i}", result) for i in range(length)])
        return result
