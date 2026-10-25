float4 main(float4 a:COLOR0):SV_Target
{
    if(dot(a.xyz,a.xyz)>0.0)return float4(normalize(a.xyz),1);
    return a;
}
