float4 main(float4 a:COLOR0):SV_Target
{
    float3 n=normalize(a.xyz);
    return dot(a.xyz,a.xyz)>0.0?float4(n,1):a;
}
