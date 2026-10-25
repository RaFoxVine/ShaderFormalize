void Cut(float x) {if(x>0.5)return;discard;}
float4 main(float4 a:COLOR0):SV_Target
{
    Cut(a.x);
    if(a.y>0.5)return a;
    return a*2;
}
