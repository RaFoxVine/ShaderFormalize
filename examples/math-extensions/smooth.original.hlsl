float3 Blend(float3 value) {
    if(value.x>0) { float unused=smoothstep(0,1,value.x); }
    if(value.x<value.x) { float dead=smoothstep(0,0,value.x); }
    return smoothstep(0.0,1.0,value);
}
float4 main(float4 a:COLOR0):SV_Target { return float4(Blend(a.xyz),1); }
