import FloatLib.Floats.Formats.BinaryInterchange.Configured.NativeDispatch
import FloatLib.Floats.Formats.BinaryInterchange.Configured.Instances
import FloatLib.Floats.Formats.BinaryInterchange.Configured.Value.CoreProof
import FloatLib.Floats.ExecFloat.Proof.Arithmetic

open FloatLib.Floats

namespace ShaderIeeePrototype

-- HLSL bit reinterpretation is distinct from a numeric conversion.
def asfloat (bits : UInt32) : Binary32 := ExecFloat.Binary.ofNatBits bits.toNat
def asuint (value : Binary32) : UInt32 := UInt32.ofNat (ExecFloat.Binary.toNatBits value)

def reference (a b : Binary32) : Binary32 :=
  ExecFloat.Spec.add (ExecFloat.Spec.mul a b) (ExecFloat.Spec.div a b)

def executable (a b : Binary32) : Binary32 := (a * b) + (a / b)

-- Reuse the upstream theorems, including their exceptional-value policy.
theorem executable_eq_reference (a b : Binary32) : executable a b = reference a b := by
  unfold executable reference
  rw [ExecFloat.Proof.add_notation_eq_spec, ExecFloat.Proof.mul_notation_eq_spec,
    ExecFloat.Proof.div_notation_eq_spec]

theorem stored_value_roundtrip (value : Binary32) :
    ExecFloat.Binary.ofNatBits (ExecFloat.Binary.toNatBits value) = value :=
  ExecFloat.Binary.ofNatBits_toNatBits value

#print axioms executable_eq_reference
#print axioms stored_value_roundtrip

def assertBits (name : String) (value : Binary32) (expected : Nat) : IO Unit := do
  let actual := ExecFloat.Binary.toNatBits value
  unless actual == expected do
    throw (IO.userError s!"{name}: expected bits {expected}, received {actual}")
  IO.println s!"PASS {name}: bits={actual}"

def assertBool (name : String) (actual expected : Bool) : IO Unit := do
  unless actual == expected do
    throw (IO.userError s!"{name}: expected {expected}, received {actual}")
  IO.println s!"PASS {name}: {actual}"

def run : IO Unit := do
  assertBits "addition" ((1.5 : Binary32) + 2.25) 0x40700000
  assertBits "subtraction" ((3.75 : Binary32) - 1.5) 0x40100000
  assertBits "multiplication" ((1.5 : Binary32) * 2) 0x40400000
  assertBits "division" ((3 : Binary32) / 2) 0x3fc00000
  assertBits "sqrt" (ExecFloat.sqrt (4 : Binary32)) 0x40000000
  let a : Binary32 := 16777216
  let b : Binary32 := 1
  let c : Binary32 := -16777216
  assertBits "reassociation-left-zero" ((a + b) + c) 0
  assertBits "reassociation-right-one" (a + (b + c)) 0x3f800000
  let positiveZero := asfloat 0
  let negativeZero := asfloat 0x80000000
  let nan := asfloat 0x7fc00123
  assertBool "zeros-numerically-equal" (positiveZero == negativeZero) true
  assertBool "zeros-bits-different" (decide (positiveZero = negativeZero)) false
  assertBool "nan-comparison-is-false" (nan == nan) false
  assertBool "nan-plus-one-is-nan" (ExecFloat.Binary.isNaN (nan + 1)) true
  assertBool "division-by-zero-is-infinity" (ExecFloat.Binary.isInfinite ((1 : Binary32) / 0)) true
  assertBool "sqrt-negative-is-nan" (ExecFloat.Binary.isNaN (ExecFloat.sqrt (-1 : Binary32))) true
  for bits in ([0, 0x80000000, 0x3f800000, 0x7f800000, 0x7fc00123, 0x00000001] : List UInt32) do
    assertBool s!"bit-roundtrip-{bits.toNat}" (asuint (asfloat bits) == bits) true
  IO.println "IEEE_PROTOTYPE_PASSED"

end ShaderIeeePrototype

def main : IO Unit := ShaderIeeePrototype.run
