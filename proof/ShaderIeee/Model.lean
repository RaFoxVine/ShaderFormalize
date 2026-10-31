import FloatLib.Floats.Formats.BinaryInterchange.Configured.NativeDispatch
import FloatLib.Floats.Formats.BinaryInterchange.Configured.Instances
import FloatLib.Floats.Formats.BinaryInterchange.Configured.Value.CoreProof
import FloatLib.Floats.ExecFloat.Proof.Arithmetic

open FloatLib.Floats

namespace ShaderIeee

abbrev Binary32 := FloatLib.Floats.Binary32
abbrev Vec (width : Nat) := Fin width → Binary32

namespace Model

-- UInt32 arithmetic wraps modulo 2^32. Its shift definitions mask the count
-- to five bits, matching the pinned DXC's explicit `and count, 31` lowering.
def uintAdd (left right : UInt32) : UInt32 := left + right
def uintSubtract (left right : UInt32) : UInt32 := left - right
def uintMultiply (left right : UInt32) : UInt32 := left * right
def uintAnd (left right : UInt32) : UInt32 := left &&& right
def uintOr (left right : UInt32) : UInt32 := left ||| right
def uintXor (left right : UInt32) : UInt32 := left ^^^ right
def uintShiftLeft (value count : UInt32) : UInt32 := value <<< count
def uintShiftRight (value count : UInt32) : UInt32 := value >>> count
def uintNot (value : UInt32) : UInt32 := ~~~value
def uintNegate (value : UInt32) : UInt32 := 0 - value

def add (left right : Binary32) : Binary32 := ExecFloat.Spec.add left right
def subtract (left right : Binary32) : Binary32 := ExecFloat.Spec.sub left right
def multiply (left right : Binary32) : Binary32 := ExecFloat.Spec.mul left right
def divide (left right : Binary32) : Binary32 := ExecFloat.Spec.div left right
def sqrt (value : Binary32) : Binary32 := ExecFloat.Spec.sqrt value

def compareLess (left right : Binary32) : Bool := ExecFloat.compareLess left right
def compareLessEqual (left right : Binary32) : Bool := ExecFloat.compareLessEqual left right
def compareGreater (left right : Binary32) : Bool := ExecFloat.compareGreater left right
def compareGreaterEqual (left right : Binary32) : Bool := ExecFloat.compareGreaterEqual left right
def compareEqual (left right : Binary32) : Bool := ExecFloat.compareEqual left right
def compareNotEqual (left right : Binary32) : Bool := ExecFloat.compareNotEqual left right

def asfloat (bits : UInt32) : Binary32 := ExecFloat.Binary.ofNatBits bits.toNat
def asuint (value : Binary32) : UInt32 :=
  UInt32.ofNatLT (ExecFloat.Binary.toNatBits value) (by
    exact FloatLib.Floats.Formats.BinaryInterchange.Model.toNatBits_lt_two_pow _)

theorem asfloat_asuint (value : Binary32) : asfloat (asuint value) = value := by
  exact ExecFloat.Binary.ofNatBits_toNatBits value

theorem asuint_asfloat (value : UInt32) : asuint (asfloat value) = value := by
  apply UInt32.toNat_inj.mp
  simp only [asuint, asfloat, UInt32.toNat_ofNatLT]
  exact ExecFloat.Binary.toNatBits_ofNatBits_of_lt value.toNat value.toNat_lt

end Model
end ShaderIeee
