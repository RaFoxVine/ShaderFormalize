float3 Direction(float3 v) { return normalize(v); }

float4 main(float4 a : COLOR0) : SV_Target
{
    if (a.x > 0.5)
        return float4(Direction(a.yzw), 1);
    return a;
}
