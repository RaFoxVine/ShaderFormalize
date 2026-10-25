void Ignore(float3 v) { }
float4 main(float4 a : COLOR0) : SV_Target
{
    Ignore(normalize(a.xyz));
    return a;
}
