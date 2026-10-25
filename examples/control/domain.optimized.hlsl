float4 main(float4 a:COLOR0):SV_Target
{
    return dot(a.xyz,a.xyz)>0.0?float4(normalize(a.xyz),1):a;
}
