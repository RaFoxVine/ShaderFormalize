float4 main(float4 a:COLOR0):SV_Target {
    float3 t=saturate(a.xyz);
    return float4(t*t*(3-2*t),1);
}
