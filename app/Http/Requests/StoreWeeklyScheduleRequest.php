<?php

namespace App\Http\Requests;

use Illuminate\Contracts\Validation\Rule;
use Illuminate\Foundation\Http\FormRequest;

class StoreWeeklyScheduleRequest extends FormRequest
{
    /**
     * Determine if the user is authorized to make this request.
     */
    public function authorize(): bool
    {
        return false;
    }

    /**
     * Get the validation rules that apply to the request.
     *
     * @return array<string, Rule|array|string>
     */
    public function rules(): array
    {
        return [
            'destination_city_code' => 'required|string|max:5',
            'destination_terminal_code' => 'required|string|max:5',
            'source_city_code' => 'required|string|max:5',
            'source_terminal_code' => 'required|string|max:5',
            'day_number' => 'required|integer|max:7|min:0',
            'travelling_time' => 'required|integer',
            'passenger_count' => 'required|integer',
            'bus_type' => 'required|string|max:5',
            'capacity' => 'requited|integer|max:30|min:20',
            'price' => 'requited|integer|max:99999999'
        ];
    }

    public function messages(): array
    {
        return [
            'destination_city_code.required' => 'destination_city_code is required by string format and max len is 5 char.',
            'destination_terminal_code.required' => 'destination_terminal_code is required by string format and max len is 5 char.',
            'source_city_code.required' => 'source_city_code is required and max len is 5 char.',
            'source_terminal_code.required' => 'source_terminal_code must be required and max len is 5 char.',
            'day_number.required' => 'day_number is integer and must be required.',
            'travelling_time.required' => 'travelling_time is integer and must be required.',
            'passenger_count.required' => 'passenger_count is integer and must be required.',
            'bus_type.required' => 'bus_type is required by string format and max len is 5 char.',
            'capacity.required' => 'capacity is integer between 20 and 30 and required.',
            'price.required' => 'price is integer and lower than 99,999,999 and required.',
        ];
    }
}
