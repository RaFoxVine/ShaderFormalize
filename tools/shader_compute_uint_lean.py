"""uint expressions share IeeeEmitter; only resource execution is added here."""
from shader_ieee_lean import IeeeEmitter, lean_type
from shader_compute_uint import uint_contract


class UintComputeEmitter(IeeeEmitter):
    def value(self, expr):
        kind = expr["kind"]
        if kind == "count":
            return "count"
        if kind == "thread":
            return "(UInt32.ofNat thread)"
        if kind == "load":
            return f"load{expr['index']}"
        return super().value(expr)

    def definition(self, name, contract):
        lines = [f"noncomputable def {name} (initial : Memory) (count : UInt32) (thread : Nat) : ThreadResult := by",
                 "  classical", "  exact Id.run do", "    let m0 : Memory := initial"]
        memory, accesses = 0, []
        for event in self.model["events"]:
            if "binding" in event:
                n = event["binding"]
                b = self.model["bindings"][n]
                lines.append(f"    let l{n} : {lean_type(b['width'])} := {self.value(b['expression'])}")
                continue
            resource = contract["bindings"][self.model["resources"][event["resource"]]["name"]]
            identity, capacity = resource["identity"], resource["capacity"]
            address = f"({self.value(event['address'])}).toNat"
            guard = f"({self.value(event['guard'])} = true)"
            write = event["kind"] == "store"
            accesses.append(f"⟨{identity}, {address}, {capacity}, {guard}, {'true' if write else 'false'}⟩")
            if write:
                lines.append(f"    let m{memory+1} := store m{memory} {guard} {identity} {address} {self.value(event['value'])}")
                memory += 1
            else:
                lines.append(f"    let load{event['index']} : UInt32 := m{memory} {identity} {address}")
        lines.append(f"    return ⟨m{memory}, [{', '.join(accesses)}]⟩")
        return "\n".join(lines)


def generate_uint_compute(original, optimized, contract):
    uint_contract(contract, original, optimized)
    lo, hi = contract["count_range"]
    return '\n\n'.join([
        'import ShaderComputeUint.Model\nnamespace ShaderComputeUint.Generated\nopen ShaderComputeUint',
        UintComputeEmitter(original).definition('original', contract),
        UintComputeEmitter(optimized).definition('optimized', contract),
        f'def threads : Nat := {original["numthreads"] * contract["dispatch_groups"]}',
        f'def inputsValid (count : UInt32) : Prop := {lo} ≤ count.toNat ∧ count.toNat ≤ {hi}',
        'def expected : Prop := ∀ (initial : Memory) (count : UInt32), inputsValid count →\n'
        '  safe threads (original initial count) ∧ safe threads (optimized initial count) ∧\n'
        '  finish threads initial (original initial count) = finish threads initial (optimized initial count)',
        'end ShaderComputeUint.Generated\n'])
