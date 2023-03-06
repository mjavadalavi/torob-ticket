<?php

namespace App\Http\Controllers\API;

use App\Enums\Status;
use App\Enums\StatusCode;
use App\Http\Controllers\Controller;
use App\Http\Requests\ListWeeklyScheduleRequest;
use App\Models\WeeklySchedule;
use Illuminate\Http\JsonResponse;
use Symfony\Component\HttpFoundation\Response;

class IndexController extends Controller
{
    /**
     * @OA\Get(
     *      path="/index",
     *      operationId="getlistItems",
     *      tags={"weekly-schedule"},
     *      summary="show list of source, destination or terminals ",
     *      description="Returns list of source, destination or terminals",
     *      @OA\Parameter(
     *          description="action of oprations each of ['terminal', 'destination', 'source']",
     *          in="path",
     *          name="action",
     *          required=true,
     *          @OA\Schema(type="string"),
     *      ),
     *     @OA\Parameter(
     *          description="city destination short-code with max 5 char",
     *          in="path",
     *          name="destination",
     *          @OA\Schema(type="string"),
     *
     *      ),
     *     @OA\Parameter(
     *          description="source city short-code with max 5 char",
     *          in="path",
     *          name="source",
     *          @OA\Schema(type="string"),
     *      ),
     *      @OA\Response(
     *          response=200,
     *          description="Successful operation",
     *       ),
     *      @OA\Response(
     *          response=404,
     *          description="Not Found",
     *      )
     *)
     */
    public function index(ListWeeklyScheduleRequest $request): JsonResponse
    {
        $data = null;
        if($request->validated()){
            switch ($request->input("action")){
                case "terminal":
                    $data = WeeklySchedule::all()->groupBy("source_city_id");
                    break;
                case "destination":
                    $data = WeeklySchedule::where("destination_city_id", $request->input("destination"))->get("source_city_id");
                    break;
                case "source":
                    $data = WeeklySchedule::where("source_city_id", $request->input("source"))->get(["source_city_id", "source_terminal_id"]);
                    break;
            }
            if ($data == null)
                return  response()->json(['status' => Status::Failed , "code" => StatusCode::Failed, "data" => $data])
                    ->header('Content-Type', 'application/json');
            else
                return response() ->json(['status' => Status::Success , "code" => StatusCode::Success, "data"=> $data])
                    ->header('Content-Type', 'application/json');
        }else{
            return  response()->json(['status' => Status::HTTP_BAD_REQUEST , "code" => StatusCode::Failed, "data"=> "your request don't have some parameter."])
                ->setStatusCode(Response::HTTP_BAD_REQUEST)
                ->header('Content-Type', 'application/json');
        }
    }

}
