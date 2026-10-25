float4 main(float4 a:COLOR0):SV_Target
{
    if(a.x<=0.0)discard;
    return float4(normalize(a.yzw),1);
}
