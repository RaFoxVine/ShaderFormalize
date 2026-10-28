"""Shared target binding and axiom audit, independent of the Lean environment."""
import re

from shader_ast import ModelError


def verification_module(generated="GeneratedModel", submitted="SubmittedProof",
                        namespace="ShaderFormalize"):
    return f'''import {generated}
import {submitted}

namespace {namespace}.Verification
theorem checked : {namespace}.Generated.expected :=
  {namespace}.AgentProof.equivalent
end {namespace}.Verification

#print axioms {namespace}.Verification.checked
'''


def audit_axioms(text, name="ShaderFormalize.Verification.checked"):
    found = re.findall(re.escape(name) + r"'? depends on axioms:\s*\[([^]]*)\]", text)
    if len(found) == 1:
        names = []
        for item in found[0].split(","):
            if item.strip():
                names.append(item.strip())
        allowed = {"propext", "Classical.choice", "Quot.sound"}
        if not set(names).issubset(allowed):
            raise ModelError(f"Proof depends on unapproved axioms: {names}", "UNPROVED")
        return names
    if name + "' does not depend on any axioms" in text or name + " does not depend on any axioms" in text:
        return []
    raise ModelError("Lean did not produce an unambiguous audit of the bound theorem", "UNPROVED")
