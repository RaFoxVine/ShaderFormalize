float4 main(float4 a:COLOR0):SV_Target
{
    bool b=a.x>0.5;
    float4 c;
    if(b) {c=ddx(a);} else {c=a;}
    return c;
}
