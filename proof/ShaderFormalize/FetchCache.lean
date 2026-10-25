import Cache.Requests

namespace ShaderFormalize.Bootstrap

-- Upstream warns about missing HTTP 404 archives without necessarily failing.
-- Keep this wrapper's successful exit tied to the complete requested set.
def requireCacheFiles (directory : System.FilePath) (hashes : Cache.IO.ModuleHashMap) : IO Unit := do
  let mut missing : Array String := #[]
  for (mod, hash) in hashes do
    let path := directory / hash.asLTar
    unless (← path.pathExists) && !(← path.isDir) do
      missing := missing.push s!"{mod}: {path}"
  unless missing.isEmpty do
    throw <| IO.userError s!"Missing {missing.size} required mathlib cache archive(s):\n{String.intercalate "\n" missing.toList}"

end ShaderFormalize.Bootstrap

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
  ShaderFormalize.Bootstrap.requireCacheFiles IO.CACHEDIR memo.hashMap
