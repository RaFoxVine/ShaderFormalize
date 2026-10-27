float3 Blend(float3 value) { return smoothstep(0.0,1.0,value); }
float4 main(float4 a:COLOR0):SV_Target {
    float unused=smoothstep(1,0,a.x);
    return float4(Blend(a.xyz),1);
}
