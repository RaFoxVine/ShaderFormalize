import Cache.Requests

-- Reuse the pinned upstream hashing/downloading code, restricted to the imports
-- we actually need. Cache.Main in this release always hashes all of Mathlib.
open Cache IO Hashing Requests System in
def main : IO Unit := CacheM.run do
  let modules := #[`Mathlib.Data.Real.Sqrt, `Mathlib.Tactic.Ring, `Mathlib.Tactic.FinCases]
  let action := modules.mapM fun mod => do
    let source ← Lean.findLean (← read).srcSearchPath mod
    getHash mod source
  let (_, memo) ← StateT.run action { rootHash := ← getRootHash }
  let parallel ← validateCurl
  validateLeanTar
  getFiles (some "leanprover-community/mathlib4") memo.hashMap false false parallel true
