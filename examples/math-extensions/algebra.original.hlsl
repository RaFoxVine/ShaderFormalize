struct Surface { float3 incident; float3 normal; };
void Shade(inout Surface s) {
    s.incident = reflect(s.incident, s.normal) + cross(s.incident, s.normal);
}
float4 main(float4 a:COLOR0, float4 b:COLOR1):SV_Target {
    Surface s; s.incident=a.xyz; s.normal=b.xyz;
    Shade(s);
    return float4(s.incident, step(a.w,a.w));
}
