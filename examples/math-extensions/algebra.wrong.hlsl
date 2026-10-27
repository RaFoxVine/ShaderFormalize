float4 main(float4 a:COLOR0, float4 b:COLOR1):SV_Target {
    float3 i=a.xyz; float3 n=b.xyz;
    float projection=i.x*n.x+i.y*n.y+i.z*n.z;
    float3 reflection=i-2*n*projection;
    float3 tangent=float3(i.y*n.z-i.z*n.y,i.z*n.x-i.x*n.z,i.x*n.y-i.y*n.x);
    // Incorrect equality boundary: HLSL step returns one when x equals edge.
    float zero=0; float one=1;
    float boundary=a.w<=a.w?zero:one;
    return float4(reflection+tangent,boundary);
}
