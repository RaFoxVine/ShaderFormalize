float4 main(float4 a : COLOR0) : SV_Target
{
    return float4(asfloat(asuint(a.x)), asfloat(asuint(a.y)),
                  asfloat(asuint(a.z)), asfloat(asuint(a.w)));
}
