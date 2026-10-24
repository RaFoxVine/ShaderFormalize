#pragma pack_matrix(column_major)
#ifdef SLANG_HLSL_ENABLE_NVAPI
#include "nvHLSLExtns.h"
#endif

#ifndef __DXC_VERSION_MAJOR
// warning X3557: loop doesn't seem to do anything, forcing loop to unroll
#pragma warning(disable : 3557)
#endif


#line 2 "D:/DTemp/Temp/shaderformalize-selection-20261024/sample.slang"
Texture2D<float4 > colorTexture_0 : register(t0);


#line 3
SamplerState samplerA_0 : register(s0);


#line 4
SamplerState samplerB_0 : register(s1);


#line 1
struct SLANG_ParameterGroup_Params_0
{
    float4 tint_0;
    float factor_0;
};


#line 1
cbuffer Params_0 : register(b0)
{
    SLANG_ParameterGroup_Params_0 Params_0;
}
float4 main(float2 uv_0 : TEXCOORD00) : SV_TARGET
{

    float4 b_0 = colorTexture_0.SampleLevel(samplerB_0, uv_0, 0.0f);
    float3 c_0 = colorTexture_0.SampleLevel(samplerA_0, uv_0, 0.0f).xyz * Params_0.tint_0.xyz;

#line 9
    float3 c_1;
    if((Params_0.factor_0) > 0.0f)
    {

#line 10
        c_1 = c_0 + b_0.xyz * Params_0.factor_0;

#line 10
    }
    else
    {

#line 10
        c_1 = c_0;

#line 10
    }
    return float4(c_1, 1.0f);
}

