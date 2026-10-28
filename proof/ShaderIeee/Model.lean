import FloatLib.Floats.Formats.BinaryInterchange.Configured.NativeDispatch
import FloatLib.Floats.Formats.BinaryInterchange.Configured.Instances
import FloatLib.Floats.Formats.BinaryInterchange.Configured.Value.CoreProof
import FloatLib.Floats.ExecFloat.Proof.Arithmetic

open FloatLib.Floats

namespace ShaderIeee

abbrev Binary32 := FloatLib.Floats.Binary32
abbrev Vec (width : Nat) := Fin width → Binary32

namespace Model

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

end Model
end ShaderIeee
